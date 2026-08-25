# gerrit-tools

Small command-line helpers for browsing and cloning Gerrit projects.

## Commands

- `gerrit ls` — list visible Gerrit projects.
- `gerrit search <keyword>` — list projects whose names contain `keyword`.
- `gerrit src <project> [target] [-b <branch>]` (also available as `gerrit clone`) — clone a project, optionally check out its
  configured tracking branch, and install Gerrit's `commit-msg` hook.

Use `-p` / `--profile` to select optional overrides. In an interactive terminal,
project lists are rendered with `batcat` (or `bat`) when available; piped output
remains one project path per line.

## Configuration

No configuration file is required: the built-in endpoint is
`review.tizen.org:29418`. In the absence of `~/.gerrit.ini`, SSH chooses the
user from its normal configuration or the current OS user, and `src` checks out `origin/tizen` by default. The configured branch is fetched
with clone, so it remains shallow. Use `src -b <branch>` to override it for one clone.

If `~/.gerrit.ini` exists, its selected profile overrides only the keys it
contains. `user` is optional. `working_branch` overrides the default; set it to an empty value
to skip the branch checkout.

```ini
[tizen]
host = other-review.example.com
port = 29418
user = alice
working_branch = origin/main
```

With multiple profiles, `--profile` is required. An explicitly selected profile
also requires that the configuration file exists.
