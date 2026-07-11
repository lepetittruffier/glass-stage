#!/bin/sh
# THE GLASS STAGE — on-system, red-free git colors. Run once.

git config --global color.diff.meta "#515151"
git config --global color.diff.frag "#6F75D7 bold"
git config --global color.diff.func "#5F5295"
git config --global color.diff.commit "#6F75D7"
git config --global color.diff.old "#8E00FF"
git config --global color.diff.new "#59C24E"
git config --global color.diff.whitespace "reverse #8E00FF"
git config --global color.status.added "#59C24E"
git config --global color.status.changed "#6F75D7"
git config --global color.status.untracked "#515151"
git config --global color.status.deleted "#8E00FF"
git config --global color.status.branch "#2CFF05"
git config --global color.decorate.branch "#2CFF05"
git config --global color.decorate.remotebranch "#6F75D7"
git config --global color.decorate.head "#8E00FF"
git config --global color.decorate.tag "#5F5295"
