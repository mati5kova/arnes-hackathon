import AppHeader from "@/components/AppHeader";
import { GripVertical } from "lucide-react";
import { Suspense, lazy, useEffect } from "react";
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";

const CHAT_PANEL_COLLAPSED_KEY = "heritage-chat-collapsed";
const PANEL_LAYOUT_AUTO_SAVE_ID = "heritage-main-layout";
const HeritageMap = lazy(() => import("@/components/HeritageMap"));
const ChatSidebar = lazy(() => import("@/components/ChatSidebar"));

const Index = () => {
	useEffect(() => {
		if (typeof window === "undefined") return;
		// Always start with chat panel open on app load.
		window.localStorage.setItem(CHAT_PANEL_COLLAPSED_KEY, "0");
	}, []);

	return (
		<div className="flex flex-col h-screen bg-background">
			<a
				href="#heritage-main-content"
				className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-3 focus:z-50 focus:rounded-md focus:bg-primary focus:px-3 focus:py-2 focus:text-primary-foreground"
			>
				Skip to main content
			</a>
			<AppHeader />

			<main
				id="heritage-main-content"
				className="flex-1 overflow-hidden"
				aria-label="Heritage map and assistant workspace"
			>
				<PanelGroup direction="horizontal" className="h-full w-full" autoSaveId={PANEL_LAYOUT_AUTO_SAVE_ID}>
					<Panel defaultSize={75} minSize={50}>
						<Suspense fallback={<div className="h-full w-full animate-pulse bg-muted/30" />}>
							<HeritageMap />
						</Suspense>
					</Panel>

					<PanelResizeHandle
						className="group relative w-2 bg-border/50 transition-colors hover:bg-border focus:outline-none"
						aria-label="Resize map and assistant panels"
					>
						<div className="absolute inset-y-0 left-1/2 -translate-x-1/2 flex items-center">
							<div className="flex h-16 w-5 items-center justify-center rounded-md border border-border/70 bg-background/90 shadow-sm transition-colors group-hover:border-muted-foreground/40">
								<GripVertical className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
							</div>
						</div>
					</PanelResizeHandle>

					<Panel
						defaultSize={25}
						minSize={20}
						maxSize={50}
						collapsible={true}
						collapsedSize={0}
						onCollapse={() => window.localStorage.setItem(CHAT_PANEL_COLLAPSED_KEY, "1")}
						onExpand={() => window.localStorage.setItem(CHAT_PANEL_COLLAPSED_KEY, "0")}
					>
						<Suspense fallback={<div className="h-full w-full animate-pulse bg-muted/30" />}>
							<ChatSidebar />
						</Suspense>
					</Panel>
				</PanelGroup>
			</main>
		</div>
	);
};

export default Index;
