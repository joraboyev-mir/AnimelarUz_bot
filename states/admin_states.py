"""FSM states for the AnimeUz admin panel."""

from aiogram.fsm.state import State, StatesGroup


class AddAnimeSG(StatesGroup):
    title = State()
    season = State()
    start_episode = State()
    status = State()
    hashtag = State()
    banner = State()
    videos = State()
    preview = State()



class ChannelSG(StatesGroup):
    add_channel = State()


class AdminManageSG(StatesGroup):
    add_admin = State()
    remove_admin = State()


class SearchSG(StatesGroup):
    query = State()


class ForwardAnimeSG(StatesGroup):
    """Admin forward qilgan video uchun preview holati."""
    preview = State()


class FeedbackSG(StatesGroup):
    text = State()


