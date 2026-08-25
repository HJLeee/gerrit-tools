import argparse
import configparser
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


class ConfigStoreTests(unittest.TestCase):
    def write_config(self, path, sections):
        config = configparser.ConfigParser()
        config.read_dict(sections)
        with path.open("w", encoding="utf-8") as output:
            config.write(output)

    def test_missing_config_uses_built_in_endpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            profile = gerrit.ConfigStore(Path(directory) / ".gerrit.ini").get_profile(None)
        self.assertEqual(profile, gerrit.Profile("review.tizen.org", "29418", None, "origin/tizen"))

    def test_profile_overrides_only_values_it_contains(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".gerrit.ini"
            self.write_config(path, {"tizen": {"user": "alice", "working_branch": "origin/main"}})
            profile = gerrit.ConfigStore(path).get_profile(None)
        self.assertEqual(profile, gerrit.Profile("review.tizen.org", "29418", "alice", "origin/main"))

    def test_requires_profile_when_multiple_exist(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".gerrit.ini"
            self.write_config(path, {"one": {}, "two": {}})
            with self.assertRaisesRegex(gerrit.ConfigurationError, "use --profile"):
                gerrit.ConfigStore(path).get_profile(None)

    def test_rejects_unknown_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(gerrit.ConfigurationError, "does not exist"):
                gerrit.ConfigStore(Path(directory) / ".gerrit.ini").get_profile("tizen")


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

    def test_list_projects_omits_user_when_not_configured(self):
        completed = subprocess.CompletedProcess([], 0, stdout="a\nb\n")
        with patch.object(gerrit.subprocess, "run", return_value=completed) as run:
            projects = gerrit.GerritClient(gerrit.Profile()).list_projects()
        self.assertEqual(projects, ["a", "b"])
        run.assert_called_once_with(
            ["ssh", "-p", "29418", "review.tizen.org", "gerrit", "ls-projects"],
            check=True, text=True, stdout=subprocess.PIPE,
        )

    def test_list_projects_uses_configured_user(self):
        profile = gerrit.Profile("review.example.com", "29418", "alice", None)
        completed = subprocess.CompletedProcess([], 0, stdout="")
        with patch.object(gerrit.subprocess, "run", return_value=completed) as run:
            gerrit.GerritClient(profile).list_projects()
        run.assert_called_once_with(
            ["ssh", "-p", "29418", "-l", "alice", "review.example.com", "gerrit", "ls-projects"],
            check=True, text=True, stdout=subprocess.PIPE,
        )

    def test_source_uses_a_depth_one_clone(self):
        profile = gerrit.Profile()
        with patch.object(gerrit.subprocess, "run") as run:
            gerrit.GerritClient(profile).clone_project("platform/core", None)
        self.assertEqual(run.call_args_list[0], call(
            ["git", "clone", "--depth", "1", "--branch", "tizen",
             "ssh://review.tizen.org:29418/platform/core", "core"], check=True
        ))

    def test_source_branch_option_overrides_the_profile(self):
        with patch.object(gerrit.subprocess, "run") as run:
            gerrit.GerritClient(gerrit.Profile()).clone_project("platform/core", None, "origin/release")
        self.assertEqual(run.call_args_list[0], call(
            ["git", "clone", "--depth", "1", "--branch", "release",
             "ssh://review.tizen.org:29418/platform/core", "core"], check=True
        ))

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

    def test_parser_registers_original_commands(self):
        parser = gerrit.build_parser()
        self.assertEqual(parser.parse_args(["ls"]).handler, gerrit.command_list)
        self.assertEqual(parser.parse_args(["search", "foo"]).handler, gerrit.command_list)
        source_args = parser.parse_args(["src", "platform/core", "-b", "release"])
        self.assertEqual(source_args.handler, gerrit.command_source)
        self.assertEqual(source_args.branch, "release")
        self.assertEqual(parser.parse_args(["clone", "platform/core"]).handler, gerrit.command_source)


if __name__ == "__main__":
    unittest.main()
