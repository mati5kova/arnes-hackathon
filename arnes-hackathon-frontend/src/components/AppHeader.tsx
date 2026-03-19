import { Info, Map, Shield } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";

const LAST_MAP_SEARCH_KEY = "heritage-last-map-search";

const AppHeader = () => {
	const location = useLocation();
	const [lastMapSearch, setLastMapSearch] = useState<string>("");
	const handleResetApp = () => {
		// Full navigation resets in-memory UI state and clears map/search query params.
		window.location.assign("/");
	};
	const mapHref = location.pathname === "/" ? `/${location.search}` : lastMapSearch ? `/${lastMapSearch}` : "/";

	useEffect(() => {
		if (typeof window === "undefined") return;
		const storedSearch = window.sessionStorage.getItem(LAST_MAP_SEARCH_KEY) || "";
		setLastMapSearch(storedSearch);
	}, []);

	useEffect(() => {
		if (typeof window === "undefined") return;
		if (location.pathname !== "/") return;
		window.sessionStorage.setItem(LAST_MAP_SEARCH_KEY, location.search);
		setLastMapSearch(location.search);
	}, [location.pathname, location.search]);

	return (
		<>
			<header
				className="h-16 border-b border-border bg-card flex items-center justify-between px-5 shrink-0"
				role="banner"
			>
				<div className="flex items-center gap-3">
					<Shield className="h-6 w-6 text-primary" aria-hidden="true" />
					<h1 className="text-xl font-semibold tracking-tight text-foreground leading-none">
						<button
							type="button"
							onClick={handleResetApp}
							aria-label="Reset app view and clear URL state"
							className="cursor-pointer rounded-sm text-left outline-none transition-opacity [transition-duration:120ms] hover:opacity-85 focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
						>
							Arnes<span className="text-primary">HACKATHON</span> #PROJECT-NAME-PLACEHOLDER#
						</button>
					</h1>
				</div>
				<nav className="flex items-center gap-1.5" aria-label="Primary navigation">
					<Link
						to={mapHref}
						aria-label="Open interactive map"
						className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-muted-foreground hover:text-foreground rounded-md hover:bg-secondary transition-colors [transition-duration:120ms]"
					>
						<Map className="h-4 w-4" aria-hidden="true" />
						<span className={location.pathname === "/" ? "text-foreground" : undefined}>Map</span>
					</Link>
					<Link
						to="/capabilities"
						aria-label="Open capabilities and roadmap page"
						className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-muted-foreground hover:text-foreground rounded-md hover:bg-secondary transition-colors [transition-duration:120ms]"
					>
						<Info className="h-4 w-4" aria-hidden="true" />
						<span className={location.pathname === "/capabilities" ? "text-foreground" : undefined}>
							Capabilities
						</span>
					</Link>
				</nav>
			</header>
		</>
	);
};

export default AppHeader;
