"""A setuptools based setup module.

See:
https://packaging.python.org/guides/distributing-packages-using-setuptools/
https://github.com/pypa/sampleproject
"""

from setuptools import setup, find_packages
from os import path

here = path.abspath(path.dirname(__file__))

with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()


setup(
    name='YoutubeSpamBot',  # Required
    version='0.0.1',  # Required
    description='Youtube spam reduction',  # Optional

    long_description=long_description,  # Optional

    url='',  # Optional

    author='Joel Christiansen',  # Optional
    packages=find_packages(),  # Required

    python_requires='>=3.6',

    install_requires=['praw'],  # Optional


    entry_points={  # Optional
        'console_scripts': [
            'youtube_spam_bot=youtube_spam_bot.entry_points:main',
        ],
    },
)
