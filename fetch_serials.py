#!/usr/bin/python3

import json
import os
import re
import time

import praw
import typer
from loguru import logger

from constants import VORON_SUBREDDIT, VORON_BOT_USERNAME, SIDEBAR_JSON_FILENAME, BOT_COMMENTS_JSON_FILENAME
from utils import format_utc

REGISTRY_RE = re.compile(r'\[([A-Z0-9\.]+)\]\(https\:\/\/redd\.it\/([0-9a-z]+)\/*\) *\(\/?u\/([^\)]+)\)')
REGISTRY_RE_2 = re.compile(r'\[([A-Z0-9\.]+)\]\(https\:\/\/www\.reddit\.com\/r\/voroncorexy\/comments\/([0-9a-z]+)\/*[0-9a-zA-Z_]*\/*\) *\(\/?u\/([^\)]+)\)')


def main(username: str = None, client_id: str = None, secret: str = None):
    assert username is not None, "Must provide --username"
    assert client_id is not None, "Must provide --client-id"
    assert secret is not None, "Must provide --secret"

    reddit = praw.Reddit(
        client_id=client_id,
        client_secret=secret,
        user_agent=f"python:voronserials:1.0 (by u/{username})",
    )

    subreddit = reddit.subreddit(VORON_SUBREDDIT)
    serialbot = reddit.redditor(VORON_BOT_USERNAME)

    if not os.path.exists(SIDEBAR_JSON_FILENAME):
        serials = {}
    else:
        serials = json.loads(open(SIDEBAR_JSON_FILENAME, 'r').read())

    logger.info(f'Fetching sidebars...')
    try:
        for widget in subreddit.widgets.sidebar:
            if isinstance(widget, praw.models.TextArea):
                for line in widget.text.split('\n'):
                    m = REGISTRY_RE.match(line)
                    if m is None:
                        m = REGISTRY_RE_2.match(line)
                    if m is None:
                        logger.info(f'No match: {line}')
                        continue
                    serial, post, user = m.group(1), m.group(2), m.group(3)
                    # V056 -> V1.056
                    if serial[:2] == 'VK':
                        serial = 'VK.' + serial[2:]
                    elif serial[0] == 'V' and serial[2] != '.':
                        serial = 'V1.' + serial[1:]
                    if serial not in serials or 'post_id' not in serials[serial]:
                        submission = reddit.submission(post)
                        logger.info(f'Serial {serial}: {post} u/{user} {format_utc(submission.created_utc)}')
                        serials[serial] = {
                            'created_utc': submission.created_utc,
                            'owner': user,
                            'post_id': submission.id
                        }
                        # rate limit API requests
                        time.sleep(1)
                    else:
                        logger.info(f'Already have serial {serial}')
    except Exception:
        logger.exception()

    ks = set(serials.keys())
    for k in ks:
        if k.startswith('V1.K'):
            del serials[k]
        elif k.startswith('V') and k[2] != '.':
            del serials[k]
        elif len(k.split('.')) == 3:
            del serials[k]

    open(SIDEBAR_JSON_FILENAME, 'w').write(json.dumps(serials))

    # The sidebar is usually not a complete list of all issued serials.
    # Fetch comments from the serial bot to fill out the list.

    logger.info(f'Fetching comments from the serial bot...')

    if not os.path.exists(BOT_COMMENTS_JSON_FILENAME):
        comments = []
    else:
        comments = json.loads(open(BOT_COMMENTS_JSON_FILENAME, 'r').read())

    comments = sorted(comments, key=lambda comment: comment['created_utc'])

    all_ids = set(comment['id'] for comment in comments)

    SERIAL_RE = re.compile(r'Congrats on ([A-Z0-9]+\.[0-9]+)\!')

    last_comment_id = comments[-1]['id'] if len(comments) > 0 else None
    logger.info(f'Starting at {last_comment_id}')

    try:
        while True:
            have_comment = False
            fetch_params = {}
            if last_comment_id is not None:
                fetch_params['before'] = 't1_' + last_comment_id
            for comment in serialbot.comments.new(params=fetch_params):
                if comment.id not in all_ids:
                    logger.info(f'New comment at {format_utc(comment.created_utc)}: {comment.body}')
                    have_comment = True
                    submission = comment.submission
                    comments.append({
                        'id': comment.id,
                        'created_utc': comment.created_utc,
                        'body': comment.body,
                        'post_id': submission.id,
                        'post_created_utc': submission.created_utc,
                        })
                    all_ids.add(comment.id)
                    last_comment_id = comment.id
                else:
                    logger.info(f'Already have comment {format_utc(comment.created_utc)}: {comment.body}')
            if not have_comment:
                break
            # Rate limit API requests
            time.sleep(1)
    except Exception:
        logger.exception()

    for comment in comments:
        m = SERIAL_RE.match(comment['body'])
        if m is not None:
            comment['serial'] = m.group(1)
        else:
            logger.warning(f'Comment does not match pattern: {comment["body"]}')

    open(BOT_COMMENTS_JSON_FILENAME, 'w').write(json.dumps(comments))
    logger.info('Done')


if __name__ == '__main__':
    typer.run(main)
