import { TooltipProvider } from "@/components/ui/tooltip";
import { LanguageProvider } from "@/lib/i18n";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Suspense, lazy } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import Index from "./pages/Index";

const Capabilities = lazy(() => import("./pages/Capabilities"));
const NotFound = lazy(() => import("./pages/NotFound"));

const queryClient = new QueryClient();

const App = () => (
	<QueryClientProvider client={queryClient}>
		<LanguageProvider>
			<TooltipProvider>
				<BrowserRouter
					future={{
						v7_startTransition: true,
						v7_relativeSplatPath: true,
					}}
				>
					<Suspense fallback={null}>
						<Routes>
							<Route path="/" element={<Index />} />
							<Route path="/capabilities" element={<Capabilities />} />
							<Route path="*" element={<NotFound />} />
						</Routes>
					</Suspense>
				</BrowserRouter>
			</TooltipProvider>
		</LanguageProvider>
	</QueryClientProvider>
);

export default App;
