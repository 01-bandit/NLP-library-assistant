import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.conversation import ConversationManager, MAX_HISTORY_MESSAGES
from backend.prompts import LIBRARY_SYSTEM_PROMPT


def check(name: str, condition: bool) -> None:
	if not condition:
		raise AssertionError(name)
	print(f"{name}: PASS")


def main() -> None:
	manager = ConversationManager()
	session_id = manager.create_session()
	check("Session creation", bool(session_id))

	manager.add_message(session_id, "user", "Is The Hobbit available?")
	manager.add_message(session_id, "assistant", "Yes, The Hobbit is available.")
	check(
		"Message storage",
		manager.get_history(session_id)
		== [
			{"role": "user", "content": "Is The Hobbit available?"},
			{"role": "assistant", "content": "Yes, The Hobbit is available."},
		],
	)

	messages = manager.build_messages(session_id)
	check(
		"System prompt",
		messages[0] == {"role": "system", "content": LIBRARY_SYSTEM_PROMPT},
	)

	for number in range(MAX_HISTORY_MESSAGES + 2):
		manager.add_message(session_id, "user", str(number))
	recent_messages = manager.build_messages(session_id)[1:]
	check(
		"History limit",
		len(recent_messages) == MAX_HISTORY_MESSAGES
		and recent_messages[0]["content"] == "2",
	)

	manager.reset_session(session_id)
	check("Reset session", manager.get_history(session_id) == [])


if __name__ == "__main__":
	try:
		main()
	except AssertionError as error:
		print(f"Test failed: {error}")
		raise SystemExit(1)
