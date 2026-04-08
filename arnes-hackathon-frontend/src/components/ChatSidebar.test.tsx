import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import ChatSidebar from "./ChatSidebar";

describe("ChatSidebar", () => {
	afterEach(() => {
		vi.restoreAllMocks();
		window.localStorage.clear();
	});

	it("loads chat models, sends a message, and renders citations", async () => {
		const fetchMock = vi
			.spyOn(globalThis, "fetch")
			.mockResolvedValueOnce(
				new Response(
					JSON.stringify({
						items: [
							{
								id: "mdml-gpt5-001",
								label: "MDML-GPT5-001",
								deployment: "MDML-GPT5-001",
								available: true,
								supportsWebSearch: true,
								isDefault: true,
								missingEnv: [],
							},
						],
						defaultModelId: "mdml-gpt5-001",
					}),
					{ status: 200, headers: { "Content-Type": "application/json" } },
				),
			)
			.mockResolvedValueOnce(
				new Response(
					JSON.stringify({
						model: {
							id: "mdml-gpt5-001",
							label: "MDML-GPT5-001",
							deployment: "MDML-GPT5-001",
							available: true,
							supportsWebSearch: true,
							isDefault: true,
							missingEnv: [],
						},
						message: {
							role: "assistant",
							content: "Here is the latest risk summary for Ptuj.",
						},
						citations: [{ title: "Ptuj flood bulletin", url: "https://example.com/ptuj" }],
						webSearchUsed: true,
						responseId: "resp_chat_1",
					}),
					{ status: 200, headers: { "Content-Type": "application/json" } },
				),
			);

		render(<ChatSidebar />);

		await screen.findByRole("option", { name: "MDML-GPT5-001" });

		fireEvent.click(screen.getByLabelText(/web search/i));
		fireEvent.change(screen.getByRole("textbox", { name: /ask the ai assistant about heritage risks/i }), {
			target: { value: "What is happening near Ptuj?" },
		});
		fireEvent.click(screen.getByRole("button", { name: /send message/i }));

		expect(await screen.findByText(/here is the latest risk summary for ptuj/i)).toBeInTheDocument();
		expect(await screen.findByRole("link", { name: /ptuj flood bulletin/i })).toHaveAttribute(
			"href",
			"https://example.com/ptuj",
		);

		await waitFor(() => {
			expect(fetchMock).toHaveBeenCalledTimes(2);
		});

		const [, secondCall] = fetchMock.mock.calls;
		expect(secondCall?.[0]).toContain("/api/chat");
		expect(secondCall?.[1]?.method).toBe("POST");
		expect(secondCall?.[1]?.body).toContain('"modelId":"mdml-gpt5-001"');
		expect(secondCall?.[1]?.body).toContain('"useWebSearch":true');
		expect(secondCall?.[1]?.body).toContain("What is happening near Ptuj?");
	});

	it("lets the user switch models before sending a message", async () => {
		const fetchMock = vi
			.spyOn(globalThis, "fetch")
			.mockResolvedValueOnce(
				new Response(
					JSON.stringify({
						items: [
							{
								id: "mdml-gpt5-001",
								label: "MDML-GPT5-001",
								deployment: "MDML-GPT5-001",
								available: true,
								supportsWebSearch: true,
								isDefault: true,
								missingEnv: [],
							},
							{
								id: "mdml-gpt4o-mini-001",
								label: "MDML-GPT4o-Mini-001",
								deployment: "MDML-GPT4o-Mini-001",
								available: true,
								supportsWebSearch: true,
								isDefault: false,
								missingEnv: [],
							},
						],
						defaultModelId: "mdml-gpt5-001",
					}),
					{ status: 200, headers: { "Content-Type": "application/json" } },
				),
			)
			.mockResolvedValueOnce(
				new Response(
					JSON.stringify({
						model: {
							id: "mdml-gpt4o-mini-001",
							label: "MDML-GPT4o-Mini-001",
							deployment: "MDML-GPT4o-Mini-001",
							available: true,
							supportsWebSearch: true,
							isDefault: false,
							missingEnv: [],
						},
						message: {
							role: "assistant",
							content: "Switched to the other model.",
						},
						citations: [],
						webSearchUsed: false,
						responseId: "resp_chat_switch",
					}),
					{ status: 200, headers: { "Content-Type": "application/json" } },
				),
			);

		render(<ChatSidebar />);

		const modelSelect = await screen.findByRole("combobox", { name: /model/i });
		fireEvent.change(modelSelect, { target: { value: "mdml-gpt4o-mini-001" } });

		fireEvent.change(screen.getByRole("textbox", { name: /ask the ai assistant about heritage risks/i }), {
			target: { value: "Use the secondary model" },
		});
		fireEvent.click(screen.getByRole("button", { name: /send message/i }));

		expect(await screen.findByText(/switched to the other model/i)).toBeInTheDocument();

		await waitFor(() => {
			expect(fetchMock).toHaveBeenCalledTimes(2);
		});

		const [, secondCall] = fetchMock.mock.calls;
		expect(secondCall?.[1]?.body).toContain('"modelId":"mdml-gpt4o-mini-001"');
	});

	it("uses a multiline composer and only submits on Enter without Shift", async () => {
		const fetchMock = vi
			.spyOn(globalThis, "fetch")
			.mockResolvedValueOnce(
				new Response(
					JSON.stringify({
						items: [
							{
								id: "mdml-gpt5-001",
								label: "MDML-GPT5-001",
								deployment: "MDML-GPT5-001",
								available: true,
								supportsWebSearch: true,
								isDefault: true,
								missingEnv: [],
							},
						],
						defaultModelId: "mdml-gpt5-001",
					}),
					{ status: 200, headers: { "Content-Type": "application/json" } },
				),
			)
			.mockResolvedValueOnce(
				new Response(
					JSON.stringify({
						model: {
							id: "mdml-gpt5-001",
							label: "MDML-GPT5-001",
							deployment: "MDML-GPT5-001",
							available: true,
							supportsWebSearch: true,
							isDefault: true,
							missingEnv: [],
						},
						message: {
							role: "assistant",
							content: "Multiline prompt received.",
						},
						citations: [],
						webSearchUsed: false,
						responseId: "resp_chat_2",
					}),
					{ status: 200, headers: { "Content-Type": "application/json" } },
				),
			);

		render(<ChatSidebar />);

		await screen.findByRole("option", { name: "MDML-GPT5-001" });

		const composer = screen.getByRole("textbox", { name: /ask the ai assistant about heritage risks/i });
		expect(composer.tagName).toBe("TEXTAREA");

		fireEvent.change(composer, {
			target: { value: "Line one\nLine two" },
		});
		fireEvent.keyDown(composer, { key: "Enter", shiftKey: true });

		expect(fetchMock).toHaveBeenCalledTimes(1);

		fireEvent.keyDown(composer, { key: "Enter" });

		expect(await screen.findByText(/multiline prompt received/i)).toBeInTheDocument();
		expect(fetchMock).toHaveBeenCalledTimes(2);

		const [, secondCall] = fetchMock.mock.calls;
		expect(secondCall?.[1]?.body).toContain("Line one\\nLine two");
	});

	it("renders assistant html safely", async () => {
		vi.spyOn(globalThis, "fetch")
			.mockResolvedValueOnce(
				new Response(
					JSON.stringify({
						items: [
							{
								id: "mdml-gpt5-001",
								label: "MDML-GPT5-001",
								deployment: "MDML-GPT5-001",
								available: true,
								supportsWebSearch: true,
								isDefault: true,
								missingEnv: [],
							},
						],
						defaultModelId: "mdml-gpt5-001",
					}),
					{ status: 200, headers: { "Content-Type": "application/json" } },
				),
			)
			.mockResolvedValueOnce(
				new Response(
					JSON.stringify({
						model: {
							id: "mdml-gpt5-001",
							label: "MDML-GPT5-001",
							deployment: "MDML-GPT5-001",
							available: true,
							supportsWebSearch: true,
							isDefault: true,
							missingEnv: [],
						},
						message: {
							role: "assistant",
							content:
								'<p><strong>Important</strong> update for <a href="https://example.com/report">Ptuj</a>.</p><script>window.__chatSidebarInjected = true</script>',
						},
						citations: [],
						webSearchUsed: false,
						responseId: "resp_chat_3",
					}),
					{ status: 200, headers: { "Content-Type": "application/json" } },
				),
			);

		render(<ChatSidebar />);

		await screen.findByRole("option", { name: "MDML-GPT5-001" });

		fireEvent.change(screen.getByRole("textbox", { name: /ask the ai assistant about heritage risks/i }), {
			target: { value: "Show formatted response" },
		});
		fireEvent.click(screen.getByRole("button", { name: /send message/i }));

		const emphasis = await screen.findByText("Important");
		expect(emphasis.tagName).toBe("STRONG");
		expect(screen.getByRole("link", { name: "Ptuj" })).toHaveAttribute("href", "https://example.com/report");
		expect(screen.queryByText(/__chatSidebarInjected/i)).not.toBeInTheDocument();
	});
});
