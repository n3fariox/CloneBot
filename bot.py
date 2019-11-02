#!/usr/bin/env python3
"""

Requires lamda layer:
arn:aws:lambda:<region>:553035198032:layer:git:6
"""
import os
import shutil
from multiprocessing import Process
from pathlib import Path
from pprint import pprint
from urllib.parse import urlparse

import git
import slack
from flask import Flask, Response
from slackeventsapi import SlackEventAdapter
from zappa.asynchronous import task

app = Flask(__name__)
SLACK_SIGNING_SECRET = os.environ['SLACK_SIGNING_SECRET']
SLACK_OAUTH_TOKEN = os.environ['SLACK_OAUTH_TOKEN']
GIT_PATH = Path('/tmp/gitrepos/')
os.makedirs(str(GIT_PATH), exist_ok=True)
slack_events_adapter = SlackEventAdapter(
    SLACK_SIGNING_SECRET, "/slack/events", app)


def send_reply(channel, user, message):
    client = slack.WebClient(token=SLACK_OAUTH_TOKEN)
    # channels starting with a "C" are a typical channel
    if channel.startswith('C'):
        client.chat_postEphemeral(channel=channel, user=user, text=message)
    else:
        client.chat_postMessage(channel=user, text=message)


def send_file(user, filepath):
    tmp = Path(filepath)
    client = slack.WebClient(token=SLACK_OAUTH_TOKEN)
    client.files_upload(file=filepath, channels=user, filename=tmp.name)


@app.route('/')
def index():
    return ''


@task
def handle_link(sender, channel, url):
    url_obj = urlparse(url)
    pth = Path(url_obj.path)
    user = pth.parts[1]
    project = pth.parts[2]
    msg = 'Yo dawg, I heard you wanted {}/{}'.format(user, project)
    send_reply(channel, sender, msg)
    shutil.rmtree(str(GIT_PATH / project), ignore_errors=True)
    try:
        repo = git.Repo.clone_from(url, str(GIT_PATH / project))
        print('Cloned')
        zipped = shutil.make_archive(
            repo.working_dir, 'gztar', GIT_PATH, project)
        print('Zipped')
        send_file(sender, zipped)
        print('File uploaded')
    except Exception as e:
        msg = str(e).replace('https://', '').replace('http://', '')
        send_reply(channel, sender, 'Error cloning repo:\n{}'.format(msg))


# Create an event listener for "reaction_added" events and print the emoji name
@slack_events_adapter.on("link_shared")
def link_shared(event_data):
    pprint(event_data)
    sender = event_data['event']['user']
    channel = event_data['event']['channel']
    links = event_data['event']['links']
    for link in links:
        handle_link(sender, channel, link['url'])
    print('done')


# Start the server on port 3000
if __name__ == "__main__":
    app.run()
