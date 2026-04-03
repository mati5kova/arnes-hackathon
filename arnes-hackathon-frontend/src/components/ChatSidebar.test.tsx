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
});
