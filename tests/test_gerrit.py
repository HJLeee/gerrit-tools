import argparse
from io import StringIO
import importlib.machinery
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import call, patch


SCRIPT = Path(__file__).resolve().parents[1] / "gerrit"
LOADER = importlib.machinery.SourceFileLoader("gerrit_tool", str(SCRIPT))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
gerrit = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = gerrit
LOADER.exec_module(gerrit)


class CommandTests(unittest.TestCase):
    def test_ls_does_not_require_keyword_argument(self):
        client = unittest.mock.Mock()
        client.list_projects.return_value = ["a/project", "b/project"]
        with patch("sys.stdout", new_callable=StringIO) as output:
            result = gerrit.command_list(argparse.Namespace(), client)
        self.assertEqual(result, 0)
        self.assertEqual(output.getvalue(), "a/project\nb/project\n")

    def test_search_filters_projects(self):
        client = unittest.mock.Mock()
        client.list_projects.return_value = ["a/project", "b/project"]
        with patch("sys.stdout", new_callable=StringIO) as output:
            result = gerrit.command_list(argparse.Namespace(keyword="b/"), client)
        self.assertEqual(result, 0)
        self.assertEqual(output.getvalue(), "b/project\n")

    def test_interactive_projects_use_batcat_when_available(self):
        output = unittest.mock.Mock()
        output.isatty.return_value = True
        with patch.object(gerrit.sys, "stdout", output), \
             patch.object(gerrit.shutil, "which", return_value="/usr/bin/batcat"), \
             patch.object(gerrit.subprocess, "run") as run:
            gerrit.render_projects(["a/project"], "Gerrit projects")
        run.assert_called_once_with(
            ["/usr/bin/batcat", "--paging=never", "--style=header,grid,numbers",
             "--file-name", "Gerrit projects", "--language=txt"],
            input="a/project\n", text=True, check=True,
        )

    def test_list_projects_uses_fixed_ssh_endpoint(self):
        completed = subprocess.CompletedProcess([], 0, stdout="a\nb\n")
        with patch.object(gerrit.subprocess, "run", return_value=completed) as run:
            projects = gerrit.GerritClient().list_projects()
        self.assertEqual(projects, ["a", "b"])
        run.assert_called_once_with(
            ["ssh", "-p", "29418", "review.tizen.org", "gerrit", "ls-projects"],
            check=True, text=True, stdout=subprocess.PIPE,
        )

    def test_source_uses_a_depth_one_clone_of_tizen(self):
        with patch.object(gerrit.subprocess, "run") as run:
            gerrit.GerritClient().clone_project("platform/core", None)
        self.assertEqual(run.call_args_list[0], call(
            ["git", "clone", "--depth", "1", "--branch", "tizen",
             "ssh://review.tizen.org:29418/platform/core", "core"], check=True
        ))
        self.assertEqual(run.call_args_list[1], call(
            ["scp", "-O", "-p", "-P", "29418",
             "review.tizen.org:hooks/commit-msg", "core/.git/hooks/"], check=True
        ))

    def test_source_branch_option_overrides_default(self):
        with patch.object(gerrit.subprocess, "run") as run:
            gerrit.GerritClient().clone_project("platform/core", None, "origin/release")
        self.assertEqual(run.call_args_list[0], call(
            ["git", "clone", "--depth", "1", "--branch", "release",
             "ssh://review.tizen.org:29418/platform/core", "core"], check=True
        ))

    def test_existing_clone_fetches_and_checks_out_requested_branch(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "core"
            (destination / ".git").mkdir(parents=True)
            results = [subprocess.CompletedProcess([], 0), subprocess.CompletedProcess([], 1),
                       subprocess.CompletedProcess([], 0), subprocess.CompletedProcess([], 0),
                       subprocess.CompletedProcess([], 0)]
            with patch.object(gerrit.subprocess, "run", side_effect=results) as run:
                gerrit.GerritClient().clone_project("platform/core", str(destination), "release")
        self.assertEqual(run.call_args_list, [
            call(["git", "fetch", "--depth", "1", "--no-tags", "origin",
                  "refs/heads/release:refs/remotes/origin/release"], check=True, cwd=destination),
            call(["git", "show-ref", "--verify", "--quiet", "refs/heads/release"],
                 check=False, cwd=destination),
            call(["git", "checkout", "-b", "release", "origin/release"], check=True, cwd=destination),
            call(["git", "config", "branch.release.remote", "origin"], check=True, cwd=destination),
            call(["git", "config", "branch.release.merge", "refs/heads/release"], check=True, cwd=destination),
        ])

    def test_parser_registers_commands_and_alias(self):
        parser = gerrit.build_parser()
        self.assertEqual(parser.parse_args(["ls"]).handler, gerrit.command_list)
        self.assertEqual(parser.parse_args(["search", "foo"]).handler, gerrit.command_list)
        source_args = parser.parse_args(["src", "platform/core", "-b", "release"])
        self.assertEqual(source_args.handler, gerrit.command_source)
        self.assertEqual(source_args.branch, "release")
        self.assertEqual(parser.parse_args(["clone", "platform/core"]).handler, gerrit.command_source)


if __name__ == "__main__":
    unittest.main()
