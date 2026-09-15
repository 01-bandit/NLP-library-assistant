const CHAT_ENDPOINT = "ws://localhost:8000/ws/chat";

const chatMessages = document.getElementById("chat-messages");
const chatForm = document.getElementById("chat-form");
const messageInput = document.getElementById("message-input");
const sendButton = document.getElementById("send-button");
const newChatButton = document.getElementById("new-chat");
const status = document.getElementById("status");
const statusText = document.getElementById("status-text");

let socket;
let sessionId = createSessionId();
let currentAssistantMessage = null;
let isGenerating = false;

function createSessionId() {
	return crypto.randomUUID();
}

function setStatus(label, state) {
	statusText.textContent = label;
	status.dataset.state = state;
}

function updateSendButton() {
	sendButton.disabled = isGenerating || (socket && socket.readyState !== WebSocket.OPEN);
}

function connect() {
	setStatus("Connecting", "connecting");
	socket = new WebSocket(CHAT_ENDPOINT);

	socket.addEventListener("open", () => {
		setStatus("Connected", "connected");
		updateSendButton();
		messageInput.focus();
	});

	socket.addEventListener("message", (event) => {
		const data = JSON.parse(event.data);

		if (data.type === "token") {
			if (!currentAssistantMessage) {
				currentAssistantMessage = addMessage("assistant", "");
			}
			currentAssistantMessage.textContent += data.content;
			scrollToBottom();
		} else if (data.type === "done") {
			isGenerating = false;
			currentAssistantMessage = null;
			updateSendButton();
			messageInput.focus();
		} else if (data.type === "error") {
			showError(data.message || "The assistant returned an error.");
			isGenerating = false;
			currentAssistantMessage = null;
			updateSendButton();
		}
	});

	socket.addEventListener("error", () => {
		setStatus("Connection error", "offline");
		updateSendButton();
	});

	socket.addEventListener("close", () => {
		if (socket) {
			setStatus("Disconnected", "offline");
		}
		isGenerating = false;
		currentAssistantMessage = null;
		updateSendButton();
	});
}

function addMessage(role, content) {
	const message = document.createElement("article");
	message.className = `message ${role}`;

	const label = document.createElement("span");
	label.className = "message-label";
	label.textContent = role === "user" ? "You" : "AI";
	label.setAttribute("aria-hidden", "true");

	const messageContent = document.createElement("div");
	messageContent.className = "message-content";
	messageContent.textContent = content;

	message.append(label, messageContent);
	chatMessages.appendChild(message);
	scrollToBottom();
	return messageContent;
}

function showError(message) {
	const errorMessage = addMessage("assistant", `Error: ${message}`);
	errorMessage.parentElement.classList.add("error-message");
}

function scrollToBottom() {
	chatMessages.scrollTop = chatMessages.scrollHeight;
}

function sendMessage() {
	const message = messageInput.value.trim();
	if (!message || isGenerating) {
		return;
	}

	if (!socket || socket.readyState === WebSocket.CLOSED) {
		connect();
	}

	addMessage("user", message);
	messageInput.value = "";
	messageInput.style.height = "auto";
	isGenerating = true;
	currentAssistantMessage = null;
	updateSendButton();

	const send = () => socket.send(JSON.stringify({ session_id: sessionId, message }));
	if (socket.readyState === WebSocket.OPEN) {
		send();
	} else {
		socket.addEventListener("open", send, { once: true });
	}
}

function startNewChat() {
	if (socket) {
		socket.close();
	}
	socket = null;
	sessionId = createSessionId();
	console.log("New chat session ID:", sessionId);
	chatMessages.innerHTML = "";
	isGenerating = false;
	currentAssistantMessage = null;
	setStatus("Ready for new chat", "connecting");
	updateSendButton();
}

chatForm.addEventListener("submit", (event) => {
	event.preventDefault();
	sendMessage();
});

messageInput.addEventListener("keydown", (event) => {
	if (event.key === "Enter" && !event.shiftKey) {
		event.preventDefault();
		sendMessage();
	}
});

messageInput.addEventListener("input", () => {
	messageInput.style.height = "auto";
	messageInput.style.height = `${Math.min(messageInput.scrollHeight, 120)}px`;
});

newChatButton.addEventListener("click", startNewChat);

connect();
