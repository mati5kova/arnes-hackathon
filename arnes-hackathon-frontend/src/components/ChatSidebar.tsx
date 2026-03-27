import { useLanguage } from "@/lib/i18n";
import { Bot, Send, User } from "lucide-react";
import { useEffect, useRef, useState } from "react";

const CHAT_INPUT_ID = "heritage-chat-input";

interface Message {
	role: "user" | "assistant";
	content: string;
}

const ChatSidebar = () => {
	const { m } = useLanguage();
	const [messages, setMessages] = useState<Message[]>([
		{
			role: "assistant",
			content: m.chat.welcome,
		},
	]);
	const [input, setInput] = useState("");
	const [loading, setLoading] = useState(false);
	const bottomRef = useRef<HTMLDivElement>(null);

	useEffect(() => {
		setMessages((prev) => {
			if (prev.length === 0) return prev;
			if (prev[0].role !== "assistant") return prev;
			return [{ ...prev[0], content: m.chat.welcome }, ...prev.slice(1)];
		});
	}, [m.chat.welcome]);

	useEffect(() => {
		bottomRef.current?.scrollIntoView({ behavior: "smooth" });
	}, [messages]);

	const handleSend = async () => {
		const text = input.trim();
		if (!text || loading) return;
		setInput("");
		const userMsg: Message = { role: "user", content: text };
		setMessages((prev) => [...prev, userMsg]);
		setLoading(true);

		// Placeholder
		setTimeout(() => {
			setMessages((prev) => [
				...prev,
				{
					role: "assistant",
					content: m.chat.demoReply,
				},
			]);
			setLoading(false);
		}, 800);
	};

	return (
		<aside
			className="h-full min-w-0 border-l border-border bg-card flex flex-col shrink-0"
			role="complementary"
			aria-label={m.chat.panelAria}
		>
			<div className="h-14 border-b border-border flex items-center gap-2.5 px-4">
				<Bot className="h-4 w-4 text-primary" aria-hidden="true" />
				<span className="text-base font-semibold text-foreground">{m.chat.title}</span>
			</div>

			<div
				className="flex-1 overflow-y-auto p-4 space-y-3.5"
				role="log"
				aria-live="polite"
				aria-relevant="additions text"
				aria-label={m.chat.conversationAria}
			>
				{messages.map((msg, i) => (
					<div
						key={i}
						className={`flex gap-2 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
						role="article"
						aria-label={msg.role === "user" ? m.chat.userMessageAria : m.chat.assistantMessageAria}
					>
						{msg.role === "assistant" && (
							<div className="w-6 h-6 rounded-full bg-primary flex items-center justify-center shrink-0 mt-0.5">
								<Bot className="h-3.5 w-3.5 text-primary-foreground" aria-hidden="true" />
							</div>
						)}
						<div
							className={`max-w-[85%] rounded-lg px-3 py-2 text-sm leading-relaxed ${
								msg.role === "user"
									? "bg-chat-user text-primary-foreground"
									: "bg-chat-bg text-foreground"
							}`}
						>
							{msg.content}
						</div>
						{msg.role === "user" && (
							<div className="w-6 h-6 rounded-full bg-muted flex items-center justify-center shrink-0 mt-0.5">
								<User className="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
							</div>
						)}
					</div>
				))}
				{loading && (
					<div className="flex gap-2" role="status" aria-live="polite">
						<div className="w-6 h-6 rounded-full bg-primary flex items-center justify-center shrink-0">
							<Bot className="h-3.5 w-3.5 text-primary-foreground" aria-hidden="true" />
						</div>
						<div className="bg-chat-bg rounded-lg px-3 py-2 text-sm text-muted-foreground">
							{m.chat.thinking}
						</div>
					</div>
				)}
				<div ref={bottomRef} aria-hidden="true" />
			</div>

			<div className="border-t border-border p-4">
				<label htmlFor={CHAT_INPUT_ID} className="sr-only">
					{m.chat.inputLabel}
				</label>
				<div className="flex gap-2">
					<input
						id={CHAT_INPUT_ID}
						name="assistantPrompt"
						type="text"
						value={input}
						onChange={(e) => setInput(e.target.value)}
						onKeyDown={(e) => e.key === "Enter" && handleSend()}
						placeholder={m.chat.inputPlaceholder}
						aria-label={m.chat.inputLabel}
						className="flex-1 bg-secondary text-sm rounded-md px-3 py-2 text-foreground placeholder:text-muted-foreground outline-none focus:ring-1 focus:ring-ring"
					/>
					<button
						type="button"
						onClick={handleSend}
						disabled={loading || !input.trim()}
						aria-label={m.chat.sendMessageAria}
						className="bg-primary text-primary-foreground rounded-md p-2 hover:opacity-90 transition-opacity [transition-duration:120ms] disabled:opacity-40"
					>
						<Send className="h-4 w-4" aria-hidden="true" />
					</button>
				</div>
			</div>
		</aside>
	);
};

export default ChatSidebar;
