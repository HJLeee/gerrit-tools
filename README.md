# gerrit-tools

Small command-line helpers for browsing and cloning projects from the Tizen
Gerrit server at `review.tizen.org:29418`. No configuration file is used.
SSH selects the account and authentication through its normal configuration.

## Commands

- `gerrit ls` — list visible Gerrit projects.
- `gerrit search <keyword>` — list projects whose names contain `keyword`.
- `gerrit src <project> [target] [-b <branch>]` — shallow-clone a project,
  install Gerrit's `commit-msg` hook, and check out `tizen` by default.
  `gerrit clone` is an alias.

Use `-b` / `--branch` to choose a branch for one clone. If its destination
already exists as a Git repository, the command shallow-fetches it without tags, creates a local branch, and explicitly sets its
upstream before checkout; this works with single-branch shallow clones too. Both `tizen` and
`origin/tizen` forms are accepted. In an interactive terminal, project lists
are rendered with `batcat` (or `bat`) when available; piped output remains one
project path per line.
