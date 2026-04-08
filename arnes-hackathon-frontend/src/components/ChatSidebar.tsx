import {
	ApiError,
	type ChatCitation,
	type ChatMessage,
	type ChatModelDescriptor,
	fetchChatModels,
	sendChatMessage,
} from "@/lib/heritage-api";
import SafeHtmlContent from "@/components/SafeHtmlContent";
import { useLanguage } from "@/lib/i18n";
import { Bot, RefreshCcw, Search, Send, User } from "lucide-react";
import { useEffect, useRef, useState } from "react";

const CHAT_INPUT_ID = "heritage-chat-input";
const CHAT_MODEL_ID = "heritage-chat-model";
const CHAT_WEB_SEARCH_ID = "heritage-chat-web-search";
const CHAT_MODEL_STORAGE_KEY = "heritage-chat-model-id";
const CHAT_WEB_SEARCH_STORAGE_KEY = "heritage-chat-web-search-enabled";
const CHAT_INPUT_MIN_HEIGHT = 44;
const CHAT_INPUT_MAX_HEIGHT = 160;

interface UiMessage extends ChatMessage {
	id: string;
	citations?: ChatCitation[];
	isWelcome?: boolean;
	webSearchUsed?: boolean;
}

const ChatSidebar = () => {
	const { m } = useLanguage();
	const [messages, setMessages] = useState<UiMessage[]>([
		{
			id: "welcome",
			role: "assistant",
			content: m.chat.welcome,
			isWelcome: true,
		},
	]);
	const [input, setInput] = useState("");
	const [loading, setLoading] = useState(false);
	const [models, setModels] = useState<ChatModelDescriptor[]>([]);
	const [selectedModelId, setSelectedModelId] = useState("");
	const [useWebSearch, setUseWebSearch] = useState(false);
	const [configError, setConfigError] = useState<string | null>(null);
	const [requestError, setRequestError] = useState<string | null>(null);
	const bottomRef = useRef<HTMLDivElement>(null);
	const composerRef = useRef<HTMLTextAreaElement>(null);

	const resizeComposer = (element: HTMLTextAreaElement) => {
		element.style.height = "auto";
		const nextHeight = Math.min(
			Math.max(element.scrollHeight, CHAT_INPUT_MIN_HEIGHT),
			CHAT_INPUT_MAX_HEIGHT,
		);
		element.style.height = `${nextHeight}px`;
		element.style.overflowY = element.scrollHeight > CHAT_INPUT_MAX_HEIGHT ? "auto" : "hidden";
	};

	useEffect(() => {
		setMessages((prev) => {
			if (prev.length === 0) return prev;
			if (!prev[0].isWelcome) return prev;
			return [{ ...prev[0], content: m.chat.welcome }, ...prev.slice(1)];
		});
	}, [m.chat.welcome]);

	useEffect(() => {
		bottomRef.current?.scrollIntoView({ behavior: "smooth" });
	}, [messages, loading]);

	useEffect(() => {
		if (!composerRef.current) return;
		resizeComposer(composerRef.current);
	}, [input]);

	useEffect(() => {
		if (typeof window === "undefined") return;
		const storedModelId = window.localStorage.getItem(CHAT_MODEL_STORAGE_KEY) || "";
		const storedWebSearch = window.localStorage.getItem(CHAT_WEB_SEARCH_STORAGE_KEY);
		if (storedModelId) {
			setSelectedModelId(storedModelId);
		}
		if (storedWebSearch === "1") {
			setUseWebSearch(true);
		}
	}, []);

	useEffect(() => {
		if (typeof window === "undefined") return;
		if (selectedModelId) {
			window.localStorage.setItem(CHAT_MODEL_STORAGE_KEY, selectedModelId);
		}
	}, [selectedModelId]);

	useEffect(() => {
		if (typeof window === "undefined") return;
		window.localStorage.setItem(CHAT_WEB_SEARCH_STORAGE_KEY, useWebSearch ? "1" : "0");
	}, [useWebSearch]);

	useEffect(() => {
		const controller = new AbortController();

		const loadModels = async () => {
			try {
				setConfigError(null);
				const response = await fetchChatModels(controller.signal);
				setModels(response.items);

				const storedModelId =
					typeof window === "undefined"
						? ""
						: window.localStorage.getItem(CHAT_MODEL_STORAGE_KEY) || "";
				const availableIds = response.items.filter((item) => item.available).map((item) => item.id);
				const preferredId =
					(storedModelId && availableIds.includes(storedModelId) && storedModelId) ||
					availableIds.find((item) => item === response.defaultModelId) ||
					availableIds[0] ||
					response.items[0]?.id ||
					"";

				setSelectedModelId(preferredId);
				if (response.items.length === 0) {
					setConfigError(m.chat.noModelsConfigured);
				} else if (availableIds.length === 0) {
					setConfigError(m.chat.noModelsAvailable);
				}
			} catch (error) {
				if (controller.signal.aborted) return;
				setConfigError(error instanceof ApiError && error.detail ? error.detail : m.chat.loadModelsFailed);
			}
		};

		void loadModels();

		return () => controller.abort();
	}, [m.chat.loadModelsFailed, m.chat.noModelsAvailable, m.chat.noModelsConfigured]);

	const availableModels = models.filter((model) => model.available);
	const selectedModel = models.find((model) => model.id === selectedModelId) || null;
	const canSend = !!input.trim() && !loading && !!selectedModel && selectedModel.available;

	const handleResetConversation = () => {
		if (loading) return;
		setMessages([
			{
				id: "welcome",
				role: "assistant",
				content: m.chat.welcome,
				isWelcome: true,
			},
		]);
		setRequestError(null);
	};

	const handleSend = async () => {
		const text = input.trim();
		if (!text || loading || !selectedModel || !selectedModel.available) return;

		const userMessage: UiMessage = {
			id: `user-${Date.now()}`,
			role: "user",
			content: text,
		};

		const requestMessages = [...messages, userMessage]
			.filter((message) => !message.isWelcome)
			.map((message) => ({ role: message.role, content: message.content }));

		setInput("");
		setRequestError(null);
		setMessages((prev) => [...prev, userMessage]);
		setLoading(true);

		try {
			const response = await sendChatMessage({
				messages: requestMessages,
				modelId: selectedModel.id,
				useWebSearch,
			});

			setMessages((prev) => [
				...prev,
				{
					id: response.responseId,
					role: "assistant",
					content: response.message.content,
					citations: response.citations,
					webSearchUsed: response.webSearchUsed,
				},
			]);
		} catch (error) {
			const detail =
				error instanceof ApiError && error.detail
					? error.detail
					: m.chat.requestFailed;
			setRequestError(detail);
		} finally {
			setLoading(false);
		}
	};

	return (
		<aside
			className="flex h-full min-w-0 shrink-0 flex-col border-l border-border bg-card"
			role="complementary"
			aria-label={m.chat.panelAria}
		>
			<div className="flex h-14 items-center gap-2.5 border-b border-border px-4">
				<Bot className="h-4 w-4 text-primary" aria-hidden="true" />
				<div className="min-w-0 flex-1">
					<span className="text-base font-semibold text-foreground">{m.chat.title}</span>
					{selectedModel?.available && (
						<p className="truncate text-xs text-muted-foreground">{selectedModel.label}</p>
					)}
				</div>
				<button
					type="button"
					onClick={handleResetConversation}
					disabled={loading}
					aria-label={m.chat.resetConversationAria}
					className="rounded-md p-2 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground disabled:opacity-40"
				>
					<RefreshCcw className="h-4 w-4" aria-hidden="true" />
				</button>
			</div>

			<div className="space-y-3 border-b border-border px-4 py-3">
				<div className="space-y-1.5">
					<label htmlFor={CHAT_MODEL_ID} className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
						{m.chat.modelLabel}
					</label>
					<select
						id={CHAT_MODEL_ID}
						value={selectedModelId}
						onChange={(event) => setSelectedModelId(event.target.value)}
						className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground outline-none focus:ring-1 focus:ring-ring"
					>
						{models.map((model) => (
							<option key={model.id} value={model.id} disabled={!model.available}>
								{model.available ? model.label : `${model.label} (${m.chat.notConfigured})`}
							</option>
						))}
					</select>
					{selectedModel && !selectedModel.available && selectedModel.missingEnv.length > 0 && (
						<p className="text-xs text-destructive">
							{m.chat.missingConfigPrefix} {selectedModel.missingEnv.join(", ")}
						</p>
					)}
				</div>

				<label
					htmlFor={CHAT_WEB_SEARCH_ID}
					className="flex cursor-pointer items-center justify-between gap-3 rounded-md border border-border bg-background px-3 py-2"
				>
					<div className="min-w-0">
						<div className="flex items-center gap-2 text-sm font-medium text-foreground">
							<Search className="h-4 w-4 text-primary" aria-hidden="true" />
							<span>{m.chat.webSearchLabel}</span>
						</div>
						<p className="mt-0.5 text-xs text-muted-foreground">{m.chat.webSearchHint}</p>
					</div>
					<input
						id={CHAT_WEB_SEARCH_ID}
						type="checkbox"
						checked={useWebSearch}
						onChange={(event) => setUseWebSearch(event.target.checked)}
						disabled={!selectedModel?.available}
						className="h-4 w-4 rounded border-border text-primary focus:ring-ring"
					/>
				</label>

				{configError && <p className="text-xs text-destructive">{configError}</p>}
			</div>

			<div
				className="flex-1 space-y-3.5 overflow-y-auto p-4"
				role="log"
				aria-live="polite"
				aria-relevant="additions text"
				aria-label={m.chat.conversationAria}
			>
				{messages.map((msg) => (
					<div
						key={msg.id}
						className={`flex gap-2 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
						role="article"
						aria-label={msg.role === "user" ? m.chat.userMessageAria : m.chat.assistantMessageAria}
					>
						{msg.role === "assistant" && (
							<div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary">
								<Bot className="h-3.5 w-3.5 text-primary-foreground" aria-hidden="true" />
							</div>
						)}
						<div
							className={`max-w-[88%] rounded-lg px-3 py-2 text-sm leading-relaxed ${
								msg.role === "user" ? "bg-chat-user text-primary-foreground" : "bg-chat-bg text-foreground"
							}`}
						>
							{msg.role === "assistant" ? (
								<SafeHtmlContent content={msg.content} />
							) : (
								<p className="whitespace-pre-wrap break-words">{msg.content}</p>
							)}
							{msg.webSearchUsed && (
								<p className="mt-2 text-[11px] uppercase tracking-wide text-muted-foreground">
									{m.chat.webSearchUsed}
								</p>
							)}
							{msg.citations && msg.citations.length > 0 && (
								<div className="mt-3 space-y-1.5 border-t border-border/70 pt-2">
									<p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
										{m.chat.sourcesLabel}
									</p>
									{msg.citations.map((citation) => (
										<a
											key={citation.url}
											href={citation.url}
											target="_blank"
											rel="noreferrer"
											className="block truncate text-xs text-primary underline-offset-2 hover:underline"
										>
											{citation.title}
										</a>
									))}
								</div>
							)}
						</div>
						{msg.role === "user" && (
							<div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-muted">
								<User className="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
							</div>
						)}
					</div>
				))}
				{loading && (
					<div className="flex gap-2" role="status" aria-live="polite">
						<div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary">
							<Bot className="h-3.5 w-3.5 text-primary-foreground" aria-hidden="true" />
						</div>
						<div className="rounded-lg bg-chat-bg px-3 py-2 text-sm text-muted-foreground">
							{m.chat.thinking}
						</div>
					</div>
				)}
				<div ref={bottomRef} aria-hidden="true" />
			</div>

			<div className="border-t border-border p-4">
				{requestError && <p className="mb-3 text-xs text-destructive">{requestError}</p>}
				<label htmlFor={CHAT_INPUT_ID} className="sr-only">
					{m.chat.inputLabel}
				</label>
				<div className="flex items-end gap-2">
					<div className="flex-1 overflow-hidden rounded-md bg-secondary focus-within:ring-1 focus-within:ring-ring">
						<textarea
							ref={composerRef}
							id={CHAT_INPUT_ID}
							name="assistantPrompt"
							rows={1}
							value={input}
							onChange={(event) => {
								setInput(event.target.value);
								resizeComposer(event.target);
							}}
							onKeyDown={(event) => {
								if (event.key !== "Enter" || event.shiftKey) return;
								event.preventDefault();
								void handleSend();
							}}
							placeholder={m.chat.inputPlaceholder}
							aria-label={m.chat.inputLabel}
							disabled={!availableModels.length}
							className="block max-h-40 min-h-[44px] w-full resize-none bg-transparent px-3 py-2 text-sm leading-6 text-foreground outline-none placeholder:text-muted-foreground disabled:opacity-50"
						/>
					</div>
					<button
						type="button"
						onClick={handleSend}
						disabled={!canSend}
						aria-label={m.chat.sendMessageAria}
						className="self-end rounded-md bg-primary p-2 text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-40"
					>
						<Send className="h-4 w-4" aria-hidden="true" />
					</button>
				</div>
			</div>
		</aside>
	);
};

export default ChatSidebar;
