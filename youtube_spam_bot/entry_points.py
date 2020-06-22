import argparse
import logging
import os.path
import re
from configparser import ConfigParser
from pathlib import Path
from textwrap import dedent
from typing import Dict, Generator, List, NamedTuple, Tuple, Union

import praw
import prawcore

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)-8s] %(message)s')
log = logging.getLogger(__name__)

YOUTUBE_LINK_REGEXES = {
    'channel': re.compile(r'''(?i)channel\/(.*?)(?:\/|\?|$)'''),
    'playlist': re.compile(r'(?<!watch).*?list=((?!videoseries).*?)(?:#|\/|\?|\&|$)'),  # noqa: E501
    'username': re.compile(r'user\/(.*)(?:\?|$|\/)'),
    'video': re.compile(r'(?:(?:watch\?.*?v=(.*?)(?:#.*)?)|youtu\.be\/(.*?)(?:\?.*)?|embed\/(.*?)(?:\?.*))(?:#|\&|\/|$)')  # noqa: E501
}

PRAW_ITEMS = Union[praw.models.Submission, praw.models.Comment]


class BotConfig(NamedTuple):
    subreddits: List[str]
    target_ratio: float
    lookback: int
    user_whitelist: List[str]


def get_content(item: PRAW_ITEMS) -> str:
    if isinstance(item, praw.models.Submission):
        if item.is_self:  # type: ignore
            return item.selftext  # type: ignore
        else:
            return item.url  # type: ignore
    if isinstance(item, praw.models.Comment):
        return item.body  # type: ignore
    raise TypeError("Can only get content for submissions of comments")


def get_youtube_ratio(redditor: praw.models.Redditor,  # type: ignore
                      lookback: int
                      ) -> Tuple[float, int]:
    found = []
    i = None
    for i, item in enumerate(redditor.new(limit=lookback)):
        content = get_content(item)
        if is_youtube(content):
            found.append(item)
    if not found:
        return 0, 0
    counted = i + 1 if i is not None else 0
    return len(found) / min(lookback, counted), counted


def is_youtube(content: str) -> bool:
    return any(pattern.search(content) for pattern in
               YOUTUBE_LINK_REGEXES.values())


def read_user_auth(target: Path) -> Dict[str, str]:
    parser = ConfigParser()
    parser.read(str(target))
    return {k: parser.get('authentication', k) for k in
            parser.options('authentication')}


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--config',
        '-c',
        type=Path,
        default=os.path.expanduser('~/.redditrc'),
        help='path for reddit user credentials')
    parser.add_argument(
        '--wiki-config-name',
        default='youtube_spam_bot_config',
        help='Name of the wiki page for runtime config')
    parser.add_argument('--dry-run', action='store_true',
                        help="don't actually remove the things")
    return parser


def get_reddit(args: argparse.Namespace) -> praw.Reddit:
    auth = read_user_auth(args.config)
    return praw.Reddit(**auth)  # type: ignore


def create_config_wiki(sub: praw.models.Subreddit, page_name: str) -> None:
    sub.wiki.create(
        page_name,
        content=dedent("""\
                [youtube_spam_bot]
                subreddits=
                target_ratio=0.33
                lookback=50
                user_whitelist="""
                       )
    )


def get_wiki_page_config(r: praw.Reddit, page_name: str) -> BotConfig:
    username = str(r.user.me())  # type: ignore
    config_sub = r.subreddit(username)
    sub_page = config_sub.wiki[page_name]  # type: ignore
    parser = ConfigParser()

    try:
        parser.read_string(sub_page.content_md)
    except prawcore.exceptions.NotFound:
        wiki_url = f'{sub_page.subreddit}/wiki/{page_name}'
        log.error((
            f"Config wiki page ({wiki_url}) not found. "
            "Creating a template then exiting."))
        create_config_wiki(config_sub, page_name)
        exit(1)
    subreddits = parser.get('youtube_spam_bot', 'subreddits').split('\n')
    # filter out potentially empty start entry
    subreddits = [s.strip() for s in subreddits if s]
    target_ratio = parser.getfloat('youtube_spam_bot', 'target_ratio')
    lookback = parser.getint('youtube_spam_bot', 'lookback')
    user_whitelist = parser.get('youtube_spam_bot',
                                'user_whitelist').split('\n')
    user_whitelist = [s.strip() for s in user_whitelist if s]
    return BotConfig(subreddits=subreddits, target_ratio=target_ratio,
                     lookback=lookback, user_whitelist=user_whitelist)


def combine_streams(*streams: praw.models.reddit.subreddit.SubredditStream
                    ) -> Generator[PRAW_ITEMS, None, None]:
    while True:
        for stream in streams:
            for item in stream:  # type: ignore
                if item is None:
                    break
                yield item


def log_removal(
        item: PRAW_ITEMS,
        ratio: float,
        counted: int,
        config: BotConfig) -> None:
    author = item.author  # type: ignore
    tr = config.target_ratio
    log.info("%-24s by %-35s ratio %s > %s over last %s posts",
             repr(item), repr(author), ratio, tr, counted)


def log_config(config: BotConfig) -> None:
    log.info("Running over subreddits: %s", config.subreddits)
    log.info("over the last %s items for lookback", config.lookback)
    log.info("with a target ratio %s", config.target_ratio)
    log.info("Whitelisted users: %s", config.user_whitelist)

def should_skip(item: PRAW_ITEMS, user_whitelist: List[str]) -> bool:
    if item.approved_by is not None:  # type: ignore
        # ignore things that have been explicitly approved
        return True
    if item.removal_reason is not None:  # type: ignore
        # ignore things that have been explicitly removed
        return True
    if item.author is None:  # type: ignore
        return True
    if item.author.name in user_whitelist:  # type: ignore
        return True
    if not is_youtube(get_content(c)):
        # ignore things that don't have youtube links
        return True
    return False

def main() -> None:
    parser = make_parser()
    args = parser.parse_args()
    r = get_reddit(args)
    i = 0
    wiki_config = get_wiki_page_config(r, args.wiki_config_name)
    log_config(wiki_config)
    grouped_subs = r.subreddit('+'.join(s for s in wiki_config.subreddits))

    streams = (grouped_subs.stream.comments(pause_after=-1),
               grouped_subs.stream.submissions(pause_after=-1))

    while True:
        try:
            for c in combine_streams(*streams):  # type: ignore
                if i % 500 == 0:
                    log.info("Have seen %s items", i)
                i += 1
                if should_skip(c, wiki_config.user_whitelist):
                    continue
                ratio, counted = get_youtube_ratio(
                    c.author,  # type: ignore
                    wiki_config.lookback)
                if ratio > wiki_config.target_ratio:
                    removal_reason = dedent(f"""\
                    This post is removed due to a high rate of self promoted
                    links. Your account may be suspended at some point by the
                    reddit admins if more than 10% of your content is pulled
                    from a single source.

                    https://www.reddit.com/wiki/selfpromotion

                    "You should submit from a variety of sources (a general
                    rule of thumb is that 10% or less of your posting and
                    conversation should link to your own content), talk to
                    people in the comments (and not just on your own links)."

                    https://www.reddit.com/wiki/faq#wiki_what_constitutes_spam.3F

                    This is an automated response due to a high rate of self
                    promoted links posted from your account.

                    Please [contact the moderators](https://www.reddit.com/message/compose?to=%2Fr%2F{c.subreddit.display_name}&subject=&message={c.permalink}) if you have questions.
                    """)
                    if not args.dry_run:
                        c.mod.remove()
                        c.mod.send_removal_message(removal_reason)
                    log_removal(c, ratio, counted, wiki_config)
        except prawcore.exceptions.ResponseException:
            log.exception("Error!")
