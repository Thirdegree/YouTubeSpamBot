# Introduction

This bot looks for users that are posting a rate of youtube posts above
a configurable ratio, and removes posts that are above that ratio as compared
to total posts. It takes into account both comments and submissions. The
account running this bot must have post permissions as a moderator of
configured subreddits.

# Configuration

## Reddit authentication
This bot expects an ini-style config file with a section 'authentication', with
the following arguments (values made up):

```ini
[authentication]
client_secret=oijsfoijasooaDOIOIJoIJ11o2w
client_id=OIJdaaoijwoiaE
password=password1
username=YouTubeSpamBot
```

The location of this file can be specified with the `--config` or `-c`
command-line argument, defaulting to `$HOME/.redditrc`.

## Runtime configuration
This runtime parameters are set in a subreddit by the same name as a bot (so
u/YouTubSpamBot would be configured in
r/YouTubSpamBot/wiki/youtube\_spam\_bot\_config).

If that page is not created at runtime, it will be created with some default
values, and the bot will exit. The config looks like this:
```ini
[youtube_spam_bot]
subreddits=
    a_subreddit
    another_subreddit
    a_third_subbie
target_ratio=0.33
lookback=50
user_whitelist=
    thirdegree
"""
```

The name of this page can be specified with the `--wiki-config-name`
command-line argument, defaulting to 'youtube\_spam\_bot\_config'
