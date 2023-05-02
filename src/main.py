import curses
import os
import re
import subprocess
from typing import NamedTuple
from xml.etree import ElementTree


class LogLineElement(NamedTuple):
    text: str
    coordinates: tuple[int, int]


def remove_colors(string: str) -> str:
    # remove ANSI color codes from a
    # https://stackoverflow.com/questions/14693701/how-can-i-remove-the-ansi-escape-sequences-from-a-string-in-pythonq
    ansi_escape = re.compile(r"\x1B[@-_][0-?]*[ -/]*[@-~]")
    return ansi_escape.sub("", string)


def is_commit_line(string: str) -> bool:
    matcher = re.compile(r"^[\|\:\s]*[o\*]")
    return matcher.match(string) is not None


def is_current_checkout(string: str) -> bool:
    matcher = re.compile(r"^[\|\:\s]*\*")
    return matcher.match(string) is not None


def remove_graphical_elements(string: str) -> str:
    matcher = re.compile(r"^[\|\:\s]*[o\*]\s*")
    return matcher.sub("", string)


def get_smartlog() -> list[str]:
    lines = subprocess.check_output(["git", "smartlog"]).decode().split("\n")
    return [remove_colors(line) for line in lines if line != ""]


def git_checkout(ref: str) -> None:
    subprocess.check_call(["git", "checkout", ref])


def draw_menu(window: curses.window, current_line: int, smartlog: list[str]) -> None:
    window.clear()
    # Define color pairs for highlighting the current line
    curses.init_pair(1, curses.COLOR_MAGENTA, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_BLACK)
    insert_row_index = 1
    # Draw the branch menu
    for i, log_line in enumerate(smartlog):
        insert_line_index = i + 1  # Pad the top of the menu by 1 line
        if i == current_line:
            window.attron(curses.color_pair(1))
            window.addstr(insert_line_index, insert_row_index, log_line)
            window.attroff(curses.color_pair(1))
        else:
            window.attron(curses.color_pair(2))
            window.addstr(insert_line_index, insert_row_index, log_line)
            window.attroff(curses.color_pair(2))
    window.refresh()


def get_elements_from_log_line(
    log_line: str,
) -> dict[str, LogLineElement]:
    retval: dict[str, LogLineElement] = {}
    matcher = re.compile(
        r"^[\|\:\s]*[o\*]\s*(?P<commit>[^\s]+)\s*(?P<author>[^\s]+)\s*(?:\((?P<branches>.*)\)\s*)?(?P<time>.*)$"
    )
    matches = matcher.search(log_line)
    if matches:
        group_dict = matches.groupdict()
        for key in group_dict.keys():
            if group_dict[key]:
                retval[key] = LogLineElement(
                    text=group_dict[key],
                    coordinates=matches.span(key),
                )
    return retval


def get_commit_or_branch_name(log_line: str) -> str:
    log_line = remove_colors(log_line).strip()

    elements = get_elements_from_log_line(log_line)

    if elements.get("branches"):
        branches = elements["branches"].text.split(",")
        branches = [branch.strip() for branch in branches]
        local_branches = [b for b in branches if not b.startswith("origin/")]
        return local_branches[0] if local_branches else branches[0]

    if elements.get("commit"):
        return elements["commit"].text

    raise ValueError("Could not find commit or branch name in log line")


def get_commit_lines_indices(lines: list[str]) -> list[int]:
    return [i for i in range(len(lines)) if is_commit_line(lines[i])]


def main(window: curses.window) -> None:
    # Hide the cursor
    curses.curs_set(0)
    # Get the list of Git branches
    smartlog = get_smartlog()

    # These are the only lines we want to interact with
    commit_lines_indices = get_commit_lines_indices(smartlog)
    current_checkout = commit_lines_indices.index(
        smartlog.index([line for line in smartlog if is_current_checkout(line)][0])
    )
    # start the at the current checkout
    current_line = current_checkout
    # Draw the initial menu
    draw_menu(window, commit_lines_indices[current_line], smartlog)
    while True:
        try:
            # Listen for user input
            key = window.getch()
            if key == curses.KEY_UP and current_line > 0:
                current_line -= 1
            elif (
                key == curses.KEY_DOWN and current_line < len(commit_lines_indices) - 1
            ):
                current_line += 1
            elif key in [curses.KEY_ENTER, 10, 13]:
                # Switch to the selected branch
                ref = get_commit_or_branch_name(
                    smartlog[commit_lines_indices[current_line]]
                )
                if current_checkout != current_line:
                    git_checkout(ref)
                break
            elif key == 27:  # Escape key
                break
            # Redraw the menu with the new selection
            draw_menu(window, commit_lines_indices[current_line], smartlog)
        except KeyboardInterrupt:
            break


if __name__ == "__main__":
    os.environ.setdefault("ESCDELAY", "1")  # exit fast on escape key
    curses.wrapper(main)
