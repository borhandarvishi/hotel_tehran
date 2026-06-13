import html
import sys
import uuid
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import streamlit as st

from agent.config import WELCOME_MESSAGE
from agent.graph import build_agent, chat
from agent.hotel_profile import get_hotel_profile

try:
    import markdown as md_lib

    def content_to_html(text: str) -> str:
        return md_lib.markdown(text, extensions=["nl2br", "sane_lists"])
except ImportError:

    def content_to_html(text: str) -> str:
        return f"<p>{html.escape(text).replace(chr(10), '<br>')}</p>"


APP_CSS = """
<style>
    .main .block-container {
        max-width: 920px;
        padding-top: 1rem;
    }

    .app-header {
        direction: rtl;
        text-align: center;
        margin-bottom: 1rem;
    }
    .app-header h1 { margin-bottom: 0.25rem; }
    .app-header p { color: #666; margin: 0; }

    .chat-wrap {
        display: flex;
        width: 100%;
        margin: 0.65rem 0;
    }
    .chat-wrap.user { justify-content: flex-end; }
    .chat-wrap.assistant { justify-content: flex-start; }

    .chat-bubble {
        direction: rtl;
        text-align: right;
        unicode-bidi: plaintext;
        max-width: 82%;
        padding: 12px 16px;
        border-radius: 18px;
        line-height: 1.65;
        font-size: 0.98rem;
        word-wrap: break-word;
    }
    .chat-bubble.user {
        background: #0088cc;
        color: #fff;
        border-bottom-right-radius: 4px;
        white-space: pre-wrap;
        box-shadow: 0 1px 2px rgba(0,0,0,0.12);
    }
    .chat-bubble.assistant {
        background: rgba(240, 240, 245, 0.95);
        color: #1a1a1a;
        border-bottom-left-radius: 4px;
        border: 1px solid rgba(0,0,0,0.08);
    }
    @media (prefers-color-scheme: dark) {
        .chat-bubble.assistant {
            background: rgba(255, 255, 255, 0.1);
            color: #f3f3f3;
            border: 1px solid rgba(255,255,255,0.12);
        }
        .app-header p { color: #aaa; }
        .hotel-rec-title { color: #e8e8e8; }
    }
    .chat-bubble.assistant p { margin: 0.35rem 0; }
    .chat-bubble.assistant ul,
    .chat-bubble.assistant ol {
        margin: 0.35rem 0;
        padding-right: 1.25rem;
        padding-left: 0;
    }

    .hotel-rec-block {
        margin: 1.25rem 0 0.75rem;
        padding-bottom: 0.75rem;
        border-bottom: 1px solid rgba(128, 128, 128, 0.25);
        width: 100%;
        box-sizing: border-box;
        clear: both;
    }
    .hotel-rec-title {
        direction: rtl;
        text-align: right;
        font-weight: 600;
        font-size: 1.05rem;
        margin-bottom: 12px;
        color: inherit;
    }
    .hotel-rec-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 14px;
        width: 100%;
        box-sizing: border-box;
    }
    .hotel-card {
        display: flex;
        flex-direction: column;
        height: 280px;
        min-height: 280px;
        max-height: 280px;
        border: 1px solid rgba(128, 128, 128, 0.35);
        border-radius: 14px;
        overflow: hidden;
        background: rgba(128, 128, 128, 0.08);
        box-sizing: border-box;
    }
    .hotel-card-img-wrap {
        position: relative;
        height: 160px;
        min-height: 160px;
        max-height: 160px;
        flex-shrink: 0;
        overflow: hidden;
        background: rgba(0, 0, 0, 0.2);
    }
    .hotel-card-img-wrap img {
        width: 100%;
        height: 160px;
        min-height: 160px;
        max-height: 160px;
        object-fit: cover;
        display: block;
    }
    .hotel-card-noimg {
        height: 160px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #888;
        direction: rtl;
        font-size: 0.85rem;
    }
    .hotel-card-body {
        flex: 1;
        min-height: 0;
        padding: 10px 12px 12px;
        direction: rtl;
        text-align: right;
        overflow: hidden;
        box-sizing: border-box;
        display: flex;
        flex-direction: column;
    }
    .hotel-card-name {
        font-weight: 600;
        font-size: 0.9rem;
        line-height: 1.4;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
        word-break: break-word;
    }
    .hotel-card-meta {
        font-size: 0.8rem;
        color: #888;
        margin-top: 6px;
        white-space: nowrap;
    }
    .hotel-card-glass-btn {
        position: absolute;
        bottom: 8px;
        left: 8px;
        right: 8px;
        z-index: 2;
        display: block;
        padding: 6px 10px;
        font-size: 0.72rem;
        font-weight: 500;
        line-height: 1.3;
        direction: rtl;
        text-align: center;
        text-decoration: none;
        color: rgba(255, 255, 255, 0.95);
        background: rgba(255, 255, 255, 0.16);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.28);
        border-radius: 9px;
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.18);
        transition: background 0.15s ease, border-color 0.15s ease,
            transform 0.1s ease;
        cursor: pointer;
    }
    .hotel-card-glass-btn:hover {
        background: rgba(255, 255, 255, 0.26);
        border-color: rgba(255, 255, 255, 0.42);
        color: #fff;
    }
    .hotel-card-glass-btn:active {
        transform: scale(0.98);
    }
    @media (prefers-color-scheme: light) {
        .hotel-card-glass-btn {
            color: rgba(20, 20, 20, 0.9);
            background: rgba(255, 255, 255, 0.62);
            border-color: rgba(255, 255, 255, 0.75);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        }
        .hotel-card-glass-btn:hover {
            background: rgba(255, 255, 255, 0.78);
        }
    }
    @media (max-width: 768px) {
        .hotel-rec-grid {
            grid-template-columns: 1fr;
        }
        .hotel-card {
            height: auto;
            min-height: 260px;
            max-height: none;
        }
    }

    [data-testid="stChatInput"] textarea {
        direction: rtl !important;
        text-align: right !important;
    }
    [data-testid="stSidebar"] {
        direction: rtl;
        text-align: right;
    }
    [data-testid="stDialog"] {
        direction: rtl;
        text-align: right;
    }
</style>
"""


@st.cache_resource
def get_agent():
    return build_agent()


def init_session():
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = str(uuid.uuid4())
    if "messages_ui" not in st.session_state:
        st.session_state.messages_ui = [
            {"role": "assistant", "content": WELCOME_MESSAGE, "hotel_ids": []}
        ]
    if "detail_hotel_id" not in st.session_state:
        st.session_state.detail_hotel_id = None


def render_user_bubble(content: str) -> None:
    safe = html.escape(content)
    st.html(
        f"""
        <div class="chat-wrap user">
            <div class="chat-bubble user">{safe}</div>
        </div>
        """
    )


def render_assistant_bubble(content: str) -> None:
    body = content_to_html(content)
    st.html(
        f"""
        <div class="chat-wrap assistant">
            <div class="chat-bubble assistant">{body}</div>
        </div>
        """
    )


def build_hotel_cards_html(profiles: list[dict], block_id: int) -> str:
    cards_html: list[str] = []
    for profile in profiles:
        hotel_id = html.escape(str(profile.get("hotel_id") or ""))
        img_url = profile.get("image_url") or ""
        if img_url:
            img_part = (
                f'<img src="{html.escape(img_url)}" alt="" loading="lazy" />'
            )
        else:
            img_part = '<div class="hotel-card-noimg">بدون تصویر</div>'

        detail_btn = (
            f'<a class="hotel-card-glass-btn" href="?hotel_id={hotel_id}">'
            "مشاهده جزئیات</a>"
        )

        name = html.escape(profile.get("name") or "")
        star = html.escape(str(profile.get("star", "—")))
        zone = html.escape(str(profile.get("tehran_zone") or ""))

        cards_html.append(
            f"""
            <div class="hotel-card">
                <div class="hotel-card-img-wrap">
                    {img_part}
                    {detail_btn}
                </div>
                <div class="hotel-card-body">
                    <div class="hotel-card-name">{name}</div>
                    <div class="hotel-card-meta">⭐ {star} | {zone}</div>
                </div>
            </div>
            """
        )

    return f"""
    <div class="hotel-rec-block" id="hotel-block-{block_id}">
        <div class="hotel-rec-title">هتل‌های پیشنهادی</div>
        <div class="hotel-rec-grid">{"".join(cards_html)}</div>
    </div>
    """


def render_hotel_cards(hotel_ids: list[str], msg_index: int) -> None:
    if not hotel_ids:
        return

    profiles = []
    for hotel_id in hotel_ids:
        profile = get_hotel_profile(hotel_id)
        if profile:
            profiles.append(profile)

    if not profiles:
        return

    with st.container(key=f"hotel_rec_{msg_index}"):
        st.html(build_hotel_cards_html(profiles, msg_index))


def open_hotel_detail_from_query() -> None:
    hotel_id = st.query_params.get("hotel_id")
    if not hotel_id:
        return
    del st.query_params["hotel_id"]
    st.session_state.detail_hotel_id = hotel_id
    st.rerun()


@st.dialog("جزئیات هتل", width="large")
def hotel_detail_dialog(hotel_id: str):
    profile = get_hotel_profile(hotel_id)
    if not profile:
        st.write("اطلاعات این هتل در دسترس نیست.")
        return

    if profile.get("image_url"):
        st.image(profile["image_url"], use_container_width=True)

    st.markdown(f"### {profile['name']}")
    st.caption(
        f"⭐ {profile.get('star', '—')} ستاره | منطقه: {profile.get('tehran_zone', '—')}"
    )

    if profile.get("score") is not None:
        st.write(f"امتیاز: {profile['score']} ({profile.get('review_count', 0)} نظر)")

    st.write(f"**آدرس:** {profile.get('address', '')}")

    if profile.get("checkin") or profile.get("checkout"):
        st.write(
            f"ورود: {profile.get('checkin', '—')} | خروج: {profile.get('checkout', '—')}"
        )

    if profile.get("popular_facilities"):
        st.write("امکانات برجسته: " + "، ".join(profile["popular_facilities"]))

    if profile.get("facilities_aggregate"):
        with st.expander("همه امکانات"):
            st.write(profile["facilities_aggregate"])

    if profile.get("description"):
        with st.expander("توضیحات"):
            st.write(profile["description"])

    gallery = profile.get("gallery_urls") or []
    if len(gallery) > 1:
        cols = st.columns(min(3, len(gallery)))
        for idx, url in enumerate(gallery[:3]):
            with cols[idx]:
                st.image(url, use_container_width=True)


def render_message(msg: dict, msg_index: int) -> None:
    role = msg["role"]
    content = msg.get("content", "")

    if role == "user":
        render_user_bubble(content)
    else:
        render_assistant_bubble(content)

    if msg.get("hotel_ids"):
        render_hotel_cards(msg["hotel_ids"], msg_index)


def main():
    st.set_page_config(page_title="دستیار هتل تهران", page_icon="🏨", layout="centered")
    st.markdown(APP_CSS, unsafe_allow_html=True)

    st.markdown(
        """
        <div class="app-header">
            <h1>دستیار رزرو هتل تهران</h1>
            <p>گفتگو کنید؛ وقتی اطلاعات کافی باشد، هتل پیشنهاد می‌دهیم.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    init_session()
    open_hotel_detail_from_query()
    agent = get_agent()

    if st.session_state.detail_hotel_id:
        hotel_detail_dialog(st.session_state.detail_hotel_id)
        st.session_state.detail_hotel_id = None

    for idx, msg in enumerate(st.session_state.messages_ui):
        render_message(msg, idx)

    user_input = st.chat_input("پیام خود را بنویسید...")
    if user_input:
        with st.spinner("در حال فکر کردن..."):
            st.session_state.messages_ui.append(
                {"role": "user", "content": user_input, "hotel_ids": []}
            )
            result = chat(agent, st.session_state.thread_id, user_input)
            st.session_state.messages_ui.append(
                {
                    "role": "assistant",
                    "content": result["content"],
                    "hotel_ids": result["hotel_ids"],
                }
            )
        st.rerun()

    with st.sidebar:
        st.subheader("سشن")
        st.text(st.session_state.thread_id[:16] + "...")
        if st.button("شروع گفتگوی جدید"):
            st.session_state.thread_id = str(uuid.uuid4())
            st.session_state.messages_ui = [
                {"role": "assistant", "content": WELCOME_MESSAGE, "hotel_ids": []}
            ]
            st.session_state.detail_hotel_id = None
            st.rerun()


if __name__ == "__main__":
    main()
