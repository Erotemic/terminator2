#!/bin/bash
__HEREDOC__='''
pip install pgi
'''
set +x

exe() { echo "\$ $@" ; "$@" ; }
exe python terminator
