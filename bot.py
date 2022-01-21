import asyncio
import logging
import os
import random
import sys
import time
from typing import Counter, Sequence
from urllib.parse import urlparse

from telethon import TelegramClient, events

logger = logging.getLogger(__name__)


def get_env(name, message, cast=str):
    if name in os.environ:
        return os.environ[name]
    while True:
        value = input(message)
        try:
            return cast(value)
        except ValueError as e:
            print(e, file=sys.stderr)
            time.sleep(1)


def setup_logger(level=logging.INFO):
    frm = (
        "%(levelname)-.3s [%(asctime)s] thr=%(thread)d %(name)s:%(lineno)d: %(message)s"
    )
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(frm))
    handler.setLevel(level)
    logger.setLevel(level)
    logger.addHandler(handler)


API_ID = get_env("TG_API_ID", "Enter your API ID: ", int)
API_HASH = get_env("TG_API_HASH", "Enter your API hash: ")
TOKEN = get_env("TG_TOKEN", "Enter the bot token: ")
NAME = TOKEN.split(":")[0]
ABSENT = 0
PRESENT = 1
CORRECT = 2
BLOCKS = {ABSENT: "⬛", PRESENT: "🟨", CORRECT: "🟩"}
MAX_TRIALS = 6
WORD_LIST = []
_chats: dict[int, tuple[str, int]] = {}


def check_with_solution(guess: str, solution: str) -> Sequence[int]:
    result = [-1] * len(solution)
    counter = Counter(solution)
    for i, l in enumerate(solution):
        if guess[i] == l:
            result[i] = CORRECT
            counter[l] -= 1
    for i, l in enumerate(guess):
        if result[i] > -1:
            continue
        elif counter.get(l, 0) > 0:
            result[i] = PRESENT
            counter[l] -= 1
        else:
            result[i] = ABSENT
    return result


async def replier(event: events.NewMessage.Event) -> None:
    logger.info(event)
    start_cmd = event.message.message.startswith("/wordle")
    chat_id = event.chat_id
    if start_cmd:
        if chat_id in _chats:
            return await event.reply("A game is ongoing, reply with your guess.")
        _chats[chat_id] = (random.choice(WORD_LIST), 0)
        return await event.reply("A new Worle game starts, reply with your guess.")
    else:
        if chat_id not in _chats:
            return await event.reply(
                "No game is ongoing, input command '/wordle' to start a new game."
            )
        solution, trials = _chats[chat_id]
        trials += 1
        guess = event.message.message.strip().lower()
        if guess not in WORD_LIST:
            return await event.reply("Not in word list.")
        elif len(guess) < len(solution):
            return await event.reply("Not enough letters.")

        result = check_with_solution(guess, solution)
        message = f"{trials}/{MAX_TRIALS}: " + "".join(map(BLOCKS.get, result))
        if all(letter == CORRECT for letter in result):
            message += "\nCongratulations, you got it!"
            del _chats[chat_id]
        elif trials == MAX_TRIALS:
            message += f"\nYou failed to find the word, it is '{solution.upper()}'."
            del _chats[chat_id]
        else:
            _chats[chat_id] = (solution, trials)
        await event.reply(message)


async def main():
    setup_logger()
    proxy = None
    if "all_proxy" in os.environ:
        parsed = urlparse(os.environ["all_proxy"])
        proxy = (parsed.scheme, parsed.hostname, parsed.port)
    bot = TelegramClient(NAME, API_ID, API_HASH, proxy=proxy)
    if not os.path.exists("word_list.txt"):
        sys.exit("You must provide the word_list.txt file.")
    with open("uniq-wordle.txt", encoding="utf-8") as f:
        WORD_LIST[:] = [line.strip() for line in f]

    await bot.start(bot_token=TOKEN)
    bot.add_event_handler(replier, events.NewMessage(incoming=True))

    try:
        await bot.run_until_disconnected()
    finally:
        await bot.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
