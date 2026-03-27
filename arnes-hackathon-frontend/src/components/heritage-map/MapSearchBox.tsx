import { useLanguage } from "@/lib/i18n";
import { getSearchSubtitle } from "@/lib/heritage-api";
import type { HeritageSiteSummary } from "@/types/heritage";
import { Search, X } from "lucide-react";
import type { KeyboardEvent } from "react";
import { useEffect, useRef, useState } from "react";
import { SEARCH_INPUT_ID, SEARCH_RESULTS_ID } from "./constants";

interface MapSearchBoxProps {
	searchQuery: string;
	onSearchQueryChange: (nextValue: string) => void;
	searchResults: HeritageSiteSummary[];
	searchLoading: boolean;
	shouldShowSearch: boolean;
	recentAndChipSearches: string[];
	onSearchSelect: (site: HeritageSiteSummary) => void;
}

const MapSearchBox = ({
	searchQuery,
	onSearchQueryChange,
	searchResults,
	searchLoading,
	shouldShowSearch,
	recentAndChipSearches,
	onSearchSelect,
}: MapSearchBoxProps) => {
	const { m } = useLanguage();
	const [activeSearchIndex, setActiveSearchIndex] = useState(-1);
	const searchInputRef = useRef<HTMLInputElement | null>(null);
	const searchItemRefs = useRef<Array<HTMLButtonElement | null>>([]);
	const showSearchDropdown = shouldShowSearch && (searchLoading || searchResults.length > 0);
	const activeSearchResult = activeSearchIndex >= 0 ? searchResults[activeSearchIndex] : undefined;
	const activeSearchOptionId =
		activeSearchIndex >= 0 ? `heritage-site-search-option-${activeSearchIndex}` : undefined;

	useEffect(() => {
		if (!shouldShowSearch) {
			setActiveSearchIndex(-1);
			return;
		}
		setActiveSearchIndex(searchResults.length > 0 ? 0 : -1);
	}, [shouldShowSearch, searchResults.length]);

	useEffect(() => {
		if (!showSearchDropdown) return;
		if (activeSearchIndex < 0) return;
		const activeItem = searchItemRefs.current[activeSearchIndex];
		activeItem?.scrollIntoView({ block: "nearest" });
	}, [activeSearchIndex, showSearchDropdown]);

	const handleSearchChipClick = (chip: string) => {
		onSearchQueryChange(chip);
		window.requestAnimationFrame(() => {
			window.requestAnimationFrame(() => {
				const input = searchInputRef.current;
				if (!input) return;
				input.focus();
				const end = input.value.length;
				input.setSelectionRange(end, end);
			});
		});
	};

	const handleSearchKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
		if (!shouldShowSearch) return;

		if (event.key === "ArrowDown") {
			event.preventDefault();
			if (searchResults.length === 0) return;
			setActiveSearchIndex((prev) => (prev + 1) % searchResults.length);
			return;
		}

		if (event.key === "ArrowUp") {
			event.preventDefault();
			if (searchResults.length === 0) return;
			setActiveSearchIndex((prev) => (prev <= 0 ? searchResults.length - 1 : prev - 1));
			return;
		}

		if (event.key === "Enter") {
			event.preventDefault();
			if (activeSearchResult) {
				onSearchSelect(activeSearchResult);
			}
			return;
		}

		if (event.key === "Escape") {
			event.preventDefault();
			onSearchQueryChange("");
			setActiveSearchIndex(-1);
		}
	};

	return (
		<div className="absolute left-12 top-3 z-[10] w-80" role="search" aria-label={m.map.search.wrapperAria}>
			<div className="relative">
				<label htmlFor={SEARCH_INPUT_ID} className="sr-only">
					{m.map.search.inputLabel}
				</label>
				<Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" aria-hidden="true" />
				<input
					ref={searchInputRef}
					id={SEARCH_INPUT_ID}
					name="heritageSiteSearch"
					type="text"
					value={searchQuery}
					onChange={(event) => onSearchQueryChange(event.target.value)}
					onKeyDown={handleSearchKeyDown}
					placeholder={m.map.search.placeholder}
					role="combobox"
					aria-label={m.map.search.inputLabel}
					aria-autocomplete="list"
					aria-expanded={showSearchDropdown}
					aria-controls={showSearchDropdown ? SEARCH_RESULTS_ID : undefined}
					aria-activedescendant={activeSearchOptionId}
					className="w-full rounded-lg border border-border bg-card/95 py-2 pl-9 pr-8 text-sm text-foreground shadow-md outline-none backdrop-blur-sm placeholder:text-muted-foreground focus:ring-1 focus:ring-ring"
				/>
				{searchQuery && (
					<button
						type="button"
						onClick={() => onSearchQueryChange("")}
						aria-label={m.map.search.clearAria}
						className="absolute right-2.5 top-2.5 text-muted-foreground hover:text-foreground"
					>
						<X className="h-4 w-4" aria-hidden="true" />
					</button>
				)}
			</div>

			<div className="mt-2 flex flex-wrap gap-1.5" role="group" aria-label={m.map.search.chipsAria}>
				{recentAndChipSearches.map((chip) => (
					<button
						key={chip}
						type="button"
						onClick={() => handleSearchChipClick(chip)}
						aria-label={`${m.map.search.useChipAriaPrefix} ${chip}`}
						className="rounded-full border border-border bg-card/95 px-2.5 py-1 text-xs text-muted-foreground transition-colors [transition-duration:120ms] hover:bg-secondary hover:text-foreground"
					>
						{chip}
					</button>
				))}
			</div>

			{showSearchDropdown && searchResults.length > 0 && (
				<div
					id={SEARCH_RESULTS_ID}
					role="listbox"
					aria-label={m.map.search.resultsAria}
					className="mt-1 max-h-72 overflow-y-auto rounded-lg border border-border bg-card/95 shadow-lg backdrop-blur-sm"
				>
					{searchResults.map((site, index) => (
						/* Only mark the active option as selected to avoid browser-specific dimming on non-active items. */
						<button
							key={site.id}
							id={`heritage-site-search-option-${index}`}
							type="button"
							role="option"
							aria-selected={activeSearchIndex === index ? true : undefined}
							ref={(element) => {
								searchItemRefs.current[index] = element;
							}}
							onClick={() => onSearchSelect(site)}
							onMouseEnter={() => setActiveSearchIndex(index)}
							aria-label={`${m.map.search.selectAriaPrefix} ${site.name}`}
							className={`flex w-full items-start gap-3 border-b border-border px-3 py-2 text-left text-sm text-foreground transition-colors [transition-duration:120ms] last:border-b-0 ${
								activeSearchIndex === index ? "bg-secondary" : "hover:bg-secondary"
							}`}
						>
							<span className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full bg-primary" />
							<div>
								<div className="font-medium text-foreground">
									{highlightText(site.name, searchQuery)}
								</div>
								<div className="text-xs text-muted-foreground">
									{highlightText(getSearchSubtitle(site) || m.map.search.fallbackSubtitle, searchQuery)}
								</div>
							</div>
						</button>
					))}
				</div>
			)}

			{showSearchDropdown && searchLoading && (
				<div
					className="mt-1 rounded-lg border border-border bg-card/95 px-3 py-2 text-sm text-muted-foreground shadow-lg backdrop-blur-sm"
					role="status"
					aria-live="polite"
				>
					{m.map.search.searching}
				</div>
			)}

			{showSearchDropdown && !searchLoading && searchResults.length === 0 && (
				<div
					className="mt-1 rounded-lg border border-border bg-card/95 px-3 py-2 text-sm text-muted-foreground shadow-lg backdrop-blur-sm"
					role="status"
					aria-live="polite"
				>
					{m.map.search.noResults}
				</div>
			)}
		</div>
	);
};

function highlightText(text: string, query: string) {
	const trimmed = query.trim();
	if (!trimmed) return text;

	const ranges = getAccentInsensitiveMatchRanges(text, trimmed);
	if (ranges.length === 0) return text;

	const parts: Array<{ text: string; highlighted: boolean }> = [];
	let cursor = 0;

	for (const range of ranges) {
		if (range.start > cursor) {
			parts.push({ text: text.slice(cursor, range.start), highlighted: false });
		}
		parts.push({ text: text.slice(range.start, range.end), highlighted: true });
		cursor = range.end;
	}

	if (cursor < text.length) {
		parts.push({ text: text.slice(cursor), highlighted: false });
	}

	return parts.map((part, index) =>
		part.highlighted ? (
			<mark key={`${part.text}-${index}`} className="rounded bg-accent/35 px-0.5 text-foreground">
				{part.text}
			</mark>
		) : (
			<span key={`${part.text}-${index}`}>{part.text}</span>
		),
	);
}

function getAccentInsensitiveMatchRanges(text: string, query: string) {
	const foldedTextMeta = foldWithIndexMap(text);
	const foldedText = foldedTextMeta.folded.toLowerCase();
	const foldedQuery = foldForSearch(query).toLowerCase();
	if (!foldedQuery) return [];

	const ranges: Array<{ start: number; end: number }> = [];
	let searchFrom = 0;

	while (searchFrom <= foldedText.length - foldedQuery.length) {
		const matchAt = foldedText.indexOf(foldedQuery, searchFrom);
		if (matchAt === -1) break;

		const startMap = foldedTextMeta.map[matchAt];
		const endMap = foldedTextMeta.map[matchAt + foldedQuery.length - 1];
		if (startMap && endMap) {
			ranges.push({ start: startMap.start, end: endMap.end });
		}

		searchFrom = matchAt + Math.max(1, foldedQuery.length);
	}

	return mergeRanges(ranges);
}

function mergeRanges(ranges: Array<{ start: number; end: number }>) {
	if (ranges.length <= 1) return ranges;
	const sorted = [...ranges].sort((a, b) => a.start - b.start);
	const merged: Array<{ start: number; end: number }> = [sorted[0]];

	for (let i = 1; i < sorted.length; i += 1) {
		const current = sorted[i];
		const last = merged[merged.length - 1];
		if (current.start <= last.end) {
			last.end = Math.max(last.end, current.end);
		} else {
			merged.push(current);
		}
	}

	return merged;
}

function foldWithIndexMap(value: string) {
	let folded = "";
	const map: Array<{ start: number; end: number }> = [];

	for (let i = 0; i < value.length; ) {
		const codePoint = value.codePointAt(i);
		if (codePoint === undefined) break;
		const char = String.fromCodePoint(codePoint);
		const charLength = char.length;
		const start = i;
		const end = i + charLength;
		const foldedChar = foldForSearch(char);

		for (let j = 0; j < foldedChar.length; j += 1) {
			map.push({ start, end });
		}

		folded += foldedChar;
		i += charLength;
	}

	return { folded, map };
}

function foldForSearch(value: string) {
	// Keep parity with backend diacritic-insensitive search behavior.
	return value
		.normalize("NFD")
		.replace(/\p{Diacritic}+/gu, "")
		.replace(/đ/gi, (match) => (match === "Đ" ? "D" : "d"));
}

export default MapSearchBox;
