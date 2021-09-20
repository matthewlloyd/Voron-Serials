#!/usr/bin/python3

import json
import os

import praw
import typer

from constants import BOT_COMMENTS_JSON_FILENAME, SIDEBAR_JSON_FILENAME


def is_V2(title):
    # Add any exceptions here
    title = title.lower()
    if 'transfer' in title:
        return False
    if 'V0.1 Serial Request'.lower() in title:
        return False
    if 'V0.0 Serial Request'.lower() in title:
        return False
    if 'V0 Serial Request'.lower() in title:
        return False
    if '2.4' in title:
        return True
    if 'v2' in title:
        return True
    return False


def main(username: str = None, client_id: str = None, secret: str = None):
    assert username is not None, "Must provide --username"
    assert client_id is not None, "Must provide --client-id"
    assert secret is not None, "Must provide --secret"

    reddit = praw.Reddit(
        client_id=client_id,
        client_secret=secret,
        user_agent=f"python:voronserials:1.0 (by u/{username})",
    )

    subreddit = reddit.subreddit('voroncorexy')

    assert os.path.exists(SIDEBAR_JSON_FILENAME), "Must run fetch_serials.py first"
    serials = json.loads(open(SIDEBAR_JSON_FILENAME, 'r').read())
    assert os.path.exists(BOT_COMMENTS_JSON_FILENAME), "Must run fetch_serials.py first"
    comments = json.loads(open(BOT_COMMENTS_JSON_FILENAME, 'r').read())

    latest_v2_utc = None
    latest_v2_num = None
    latest_v2_post_id = None
    for serial, details in serials.items():
        if not serial.startswith('V2.'):
            continue
        if latest_v2_utc is None or details['created_utc'] > latest_v2_utc:
            latest_v2_utc = details['created_utc']
            latest_v2_num = serial
            latest_v2_post_id = details['post_id']

    for comment in comments:
        if not comment['serial'].startswith('V2.'):
            continue
        if latest_v2_utc is None or comment['post_created_utc'] > latest_v2_utc:
            latest_v2_utc = comment['post_created_utc']
            latest_v2_num = comment['serial']
            latest_v2_post_id = comment['post_id']

    print(f'Last serial number issued: {latest_v2_utc} {latest_v2_num} {latest_v2_post_id}')
    print()

    queue = []

    print(f'Queue:')
    last_post_id = None
    while True:
        have_post = False
        fetch_params = {}
        if last_post_id is not None:
            fetch_params['after'] = 't3_' + last_post_id
        for post in subreddit.new(params=fetch_params):
            have_post = True
            last_post_id = post.id
            if post.link_flair_text != 'Serial Request:snoo_scream:':
                continue
            if post.created_utc <= latest_v2_utc:
                have_post = False
                break
            type_str = "V2.4" if is_V2(post.title) else "other"
            queue.append({
                'title': post.title,
                'created_utc': post.created_utc,
                'id': post.id,
                'guessed_type': type_str,
            })
        if not have_post:
            break

    queue = sorted(queue, key=lambda p: p['created_utc'])

    for post in queue:
        print(f'{post["created_utc"]}: {post["guessed_type"]:<5s} "{post["title"]}" https://reddit.com/{post["id"]}')

    queue = [post for post in queue if post['guessed_type'] == "V2.4"]

    # This list of rejects needs to be actively maintained for the predictions
    # to be accurate.
    rejects = set()
    # For example, if you think the post with ID po8ci8 is going to be rejected,
    # then add it to the set:
    # rejects.add('po8ci8')

    # Then, you can set the UTC here of rejects that you have checked so far.
    # The script will show you which entries you need to check.
    rejects_checked_through = 1631821827

    print('\nPredictions:')
    current_num = int(latest_v2_num.split('.')[1]) + 1
    reject_message = False
    for entry in queue:
        if entry['id'] in rejects:
            print(f'Reject: {entry["created_utc"]} {entry["title"]} https://reddit.com/{entry["id"]}')
            continue
        if entry["created_utc"] > rejects_checked_through and not reject_message:
            print('Rejects not checked:')
            reject_message = True
        print(f'V2.{current_num}: {entry["created_utc"]} {entry["title"]} https://reddit.com/{entry["id"]}')
        current_num += 1


if __name__ == '__main__':
    typer.run(main)
