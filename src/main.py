import curses
from enum import Enum
import os
import re
import subprocess
from typing import NamedTuple


class LogLineElement(NamedTuple):
    text: str
    coordinates: tuple[int, int]


class Colors(Enum):
    WHITE = 1
    MAGENTA = 2
    YELLOW = 3
    GREEN = 4


def initialize_curses() -> None:
    # Hide the cursor
    curses.curs_set(0)

    # Define color pairs for highlighting the current line
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_WHITE, -1)
    curses.init_pair(2, curses.COLOR_MAGENTA, -1)
    curses.init_pair(3, curses.COLOR_YELLOW, -1)
    curses.init_pair(4, curses.COLOR_GREEN, -1)


def get_smartlog() -> list[str]:
    lines = subprocess.check_output(["git", "smartlog"]).decode().split("\n")
    return [remove_colors(line) for line in lines if line != ""]


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


def git_checkout(ref: str) -> None:
    subprocess.check_call(["git", "checkout", ref])


def format_line(
    log_line: str,
    window: curses.window,
    insert_line_index: int,
    is_current_line: bool = False,
) -> None:
    insert_row_index = 1
    if is_current_line:
        color_screen_text(
            log_line, window, insert_line_index, insert_row_index, Colors.MAGENTA
        )
    else:
        # first colorize the whole thing white
        color_screen_text(log_line, window, insert_line_index, insert_row_index)

        # colorize specific elements
        elements = get_elements_from_log_line(log_line)
        if elements.get("commit"):
            color_screen_text(
                elements["commit"].text,
                window,
                insert_line_index,
                elements["commit"].coordinates[0] + 1,
                Colors.YELLOW,
            )
        if elements.get("branches"):
            color_screen_text(
                f"({elements['branches'].text})",
                window,
                insert_line_index,
                elements["branches"].coordinates[0],
                Colors.GREEN,
            )


def color_screen_text(
    text: str,
    window: curses.window,
    insert_line_index: int,
    insert_row_index: int = 1,
    color: Colors = Colors.WHITE,
) -> None:
    window.attron(curses.color_pair(color.value))
    window.addstr(insert_line_index, insert_row_index, text)
    window.attroff(curses.color_pair(color.value))


def draw_menu(window: curses.window, current_line: int, smartlog: list[str]) -> None:
    window.clear()

    # Draw the branch menu
    for i, log_line in enumerate(smartlog):
        format_line(log_line, window, i + 1, i == current_line)
    window.refresh()


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
    initialize_curses()
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
