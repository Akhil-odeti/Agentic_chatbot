"""Chainlit UI: sign in with your OpenAI key, per-key chat history (thread UUIDs), per-chat agent
memory, charts in the side panel."""
import chainlit as cl
from chainlit.input_widget import Select
import plotly.io as pio
from chainlit.data.sql_alchemy import SQLAlchemyDataLayer
from chainlit.types import ThreadDict
from langchain_core.messages import AIMessageChunk, ToolMessage

import config
import key_auth
from agent import build_agent, get_saver
from db_init import init_chat_db
from local_storage import LocalStorageClient
from openai_models import KeyRejected, friendly_error, list_chat_models, pick_model
from tools import PENDING, PLANS, SEARCH_DEPTH_CHOICE

init_chat_db(config.CHAT_DB)


@cl.data_layer
def data_layer():
    return SQLAlchemyDataLayer(
        conninfo=f"sqlite+aiosqlite:///{config.CHAT_DB}",
        storage_provider=LocalStorageClient(config.CHART_STORE_DIR),
    )


@cl.password_auth_callback
async def sign_in(username: str, password: str) -> cl.User | None:
    """The login form's password field takes the OpenAI API key. The key proves who the user is:
    the same key always maps to the same user id, so its chat history comes back on every visit.
    The username is only a display name. The key is checked with OpenAI, then kept in server
    memory (key_auth) and never written to the database."""
    key = (password or "").strip()
    if not key_auth.looks_like_key(key):
        return None
    try:
        await list_chat_models(key)
    except KeyRejected:
        return None  # OpenAI says the key is invalid
    user_id = key_auth.identity_for(key)
    key_auth.remember(user_id, key)
    return cl.User(
        identifier=user_id,
        display_name=(username or "").strip() or "You",
        metadata={"role": "user"},  # metadata is stored in the database: never put the key here
    )


def _plotly_elements(charts: list[dict]) -> list[cl.Plotly]:
    return [
        cl.Plotly(name=c["spec"]["title"], figure=pio.from_json(c["fig_json"]), display="side")
        for c in charts
    ]


def _api_key() -> str:
    """The key this user signed in with, or "" if the server no longer holds it (it was restarted).
    Never copy it into cl.user_session: that is written to the database."""
    user = cl.user_session.get("user")
    return key_auth.recall(getattr(user, "identifier", None))


SIGN_IN_AGAIN = (
    "The server no longer holds your OpenAI key (it was restarted). Open your profile menu, "
    "choose Logout, then sign in again with the same key. Your chats are kept."
)


def _chosen_model() -> str | None:
    return (cl.user_session.get("chat_settings") or {}).get("model")


async def _show_model_picker() -> tuple[str, bool]:
    """Ask OpenAI which chat models this key can use and show them as a dropdown in the chat
    settings. Returns (selected model, whether the key looked valid)."""
    key_ok = True
    try:
        result = await list_chat_models(_api_key())
        models = result.models
        if result.status == "unreachable":
            await cl.Message(
                content="I could not reach OpenAI to check your key, so common models are listed."
            ).send()
    except KeyRejected:
        key_ok, models = False, list(config.FALLBACK_MODELS)
        await cl.Message(
            content="OpenAI rejected your API key. Open your profile menu, choose Logout and "
            "sign in again with a valid key."
        ).send()
    model = pick_model(models, _chosen_model())
    await cl.ChatSettings(
        [
            Select(
                id="model",
                label="Model",
                values=models,
                initial_value=model,
                description="Models your OpenAI key can use. Applies to your next message.",
            )
        ]
    ).send()
    return model, key_ok


@cl.on_chat_start
async def on_start():
    if not _api_key():
        await cl.Message(content=SIGN_IN_AGAIN).send()
        return
    model, key_ok = await _show_model_picker()
    if key_ok:
        await cl.Message(
            content=f"Ready. Using **{model}** with your OpenAI key. To change the model, open the "
            "settings icon next to the message box."
        ).send()


@cl.on_chat_resume
async def on_resume(thread: ThreadDict):
    """Nothing to rebuild: messages and charts are loaded from the data layer, and the agent's
    memory is restored automatically because the thread_id is the same in the checkpointer.
    Only the model dropdown is shown again (the last model chosen in this chat is kept)."""
    if not _api_key():
        await cl.Message(content=SIGN_IN_AGAIN).send()
        return
    await _show_model_picker()


@cl.on_message
async def on_message(message: cl.Message):
    thread_id = cl.context.session.thread_id
    key = _api_key()
    if not key:
        await cl.Message(
            content=SIGN_IN_AGAIN
        ).send()
        return
    agent = build_agent(await get_saver(), key, _chosen_model() or config.DEFAULT_MODEL)
    run_config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": 2 * (config.MAX_RETRIES + 1) + 8,  # +2 for the plan_charts step
    }
    reply = cl.Message(content="")
    await reply.send()  # one message per turn: tool steps, streamed text and charts all attach to it
    PENDING.pop(thread_id, None)
    PLANS.pop(thread_id, None)  # the chart-selector plans again on each new request
    SEARCH_DEPTH_CHOICE.pop(thread_id, None)  # ask for search depth again on each new question
    steps_by_index: dict[int, cl.Step] = {}  # tool call index -> UI step (current model turn)
    steps_by_id: dict[str, cl.Step] = {}
    args_buf: dict[int, str] = {}
    group: cl.Step | None = None
    used: list[str] = []
    children: list[cl.Step] = []
    try:
        async for chunk, meta in agent.astream(
            {"messages": [{"role": "user", "content": message.content}]},
            run_config,
            stream_mode="messages",
        ):
            if isinstance(chunk, AIMessageChunk) and meta.get("langgraph_node") == "model":
                for tc in chunk.tool_call_chunks or []:
                    idx = tc.get("index") or 0
                    if tc.get("name"):  # first chunk of a tool call: show it in the UI
                        if group is None:
                            # One parent step per turn. Chainlit draws an avatar for every tool step directly
                            # under a message, but not for steps nested inside another step, so grouping
                            # gives a single icon with all tool calls inside its dropdown.
                            group = cl.Step(name="Tools", type="tool", parent_id=reply.id)
                            await group.send()
                        used.append(tc["name"])
                        step = cl.Step(name=tc["name"], type="tool", show_input="json", parent_id=group.id)
                        await step.send()
                        children.append(step)
                        steps_by_index[idx] = step
                        args_buf[idx] = ""
                        if tc.get("id"):
                            steps_by_id[tc["id"]] = step
                    if tc.get("args") and idx in args_buf:
                        args_buf[idx] += tc["args"]
                # chunk.text is the plain text of this chunk. The Responses API returns content as a
                # list of blocks (text, reasoning), so chunk.content is not always a string.
                text = str(chunk.text)
                if text:
                    await reply.stream_token(text)
            elif isinstance(chunk, ToolMessage):
                step = steps_by_id.get(chunk.tool_call_id)
                if step is not None:
                    idx = next((i for i, st in steps_by_index.items() if st is step), None)
                    step.input = args_buf.get(idx, "")
                    step.output = str(chunk.content)
                    await step.update()
                    if idx is not None:
                        steps_by_index.pop(idx, None)
    except Exception as e:
        reply.content += "\n\n" + friendly_error(e, key)
        await reply.update()
        return
    finally:
        if group is not None:
            if len(children) == 1:
                # Single tool call: show that call as the one dropdown instead of a wrapper plus a child.
                only = children[0]
                group.name, group.show_input = only.name, "json"
                group.input, group.output = only.input, only.output
                await only.remove()
            else:
                group.name = ", ".join(dict.fromkeys(used))
            await group.update()

    charts = PENDING.pop(thread_id, [])
    # A recolor/regenerate of the same chart title replaces the earlier one in the same turn.
    latest = {c["spec"]["title"]: c for c in charts}
    charts = list(latest.values())
    if charts:
        reply.elements = _plotly_elements(charts)
        # Chainlit turns an element's name in the message text into a link that (re)opens the side
        # panel, so the user can always get the charts back after closing it.
        links = "  |  ".join(el.name for el in reply.elements)
        reply.content += f"\n\n**Open charts:** {links}"
        reply.metadata = {"chart_specs": [c["spec"] for c in charts]}
    if not reply.content and not charts:
        reply.content = "(no response)"
    await reply.update()
