import curses
import os
import re
import subprocess


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


def draw_menu(window: curses.window, current_row: int, smartlog: list[str]) -> None:
    window.clear()
    # Define color pairs for highlighting the current row
    curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_BLACK)
    # Draw the branch menu
    for i, branch in enumerate(smartlog):
        x = 2
        y = i + 2
        if i == current_row:
            window.attron(curses.color_pair(1))
            window.addstr(y, x, f" {branch} ", curses.A_REVERSE)
            window.attroff(curses.color_pair(1))
        else:
            window.attron(curses.color_pair(2))
            window.addstr(y, x, f" {branch} ")
            window.attroff(curses.color_pair(2))
    window.refresh()


def get_commit_or_branch_name(log_row: str) -> str:
    log_row = remove_colors(log_row).strip()
    log_row = remove_graphical_elements(log_row)
    parts_without_commit_and_author = [
        part for part in log_row.split(" ") if part != ""
    ][2:]
    if parts_without_commit_and_author[0].startswith("("):
        branches: list[str] = []
        index = 0
        while True:
            part = parts_without_commit_and_author[index].rstrip(",")
            if part.startswith("("):
                branches.append(part.lstrip("("))
            elif part.endswith(")"):
                branches.append(part.rstrip(")"))
                break
            else:
                branches.append(part)
            index += 1
        local_branches = [b for b in branches if not b.startswith("origin/")]
        print(local_branches)
        return local_branches[0] if local_branches else branches[0]

    # return commit hash
    return log_row.split(" ")[0]


def get_commit_lines_indices(lines: list[str]) -> list[int]:
    return [i for i in range(len(lines)) if is_commit_line(lines[i])]


def main(window: curses.window) -> None:
    # Hide the cursor
    curses.curs_set(0)
    # Get the list of Git branches
    smartlog = get_smartlog()

    # These are the only lines we want to interact with
    commit_lines_indices = get_commit_lines_indices(smartlog)
    current_row = commit_lines_indices.index(
        smartlog.index([line for line in smartlog if is_current_checkout(line)][0])
    )
    # Draw the initial menu
    draw_menu(window, commit_lines_indices[current_row], smartlog)
    while True:
        try:
            # Listen for user input
            key = window.getch()
            if key == curses.KEY_UP and current_row > 0:
                current_row -= 1
            elif key == curses.KEY_DOWN and current_row < len(commit_lines_indices) - 1:
                current_row += 1
            elif key in [curses.KEY_ENTER, 10, 13]:
                # Switch to the selected branch
                ref = get_commit_or_branch_name(
                    smartlog[commit_lines_indices[current_row]]
                )
                git_checkout(ref)
                break
            elif key == 27:  # Escape key
                break
            # Redraw the menu with the new selection
            draw_menu(window, commit_lines_indices[current_row], smartlog)
        except KeyboardInterrupt:
            break


if __name__ == "__main__":
    os.environ.setdefault("ESCDELAY", "1")  # exit fast on escape key
    curses.wrapper(main)
