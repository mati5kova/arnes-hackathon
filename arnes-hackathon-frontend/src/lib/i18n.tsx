/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

export type Language = "sl" | "en";

const LANGUAGE_STORAGE_KEY = "heritage-language";

export const messages = {
    en: {
        header: {
            resetAppAria: "Reset app view and clear URL state",
            navAria: "Primary navigation",
            openMapAria: "Open interactive map",
            openCapabilitiesAria: "Open capabilities and roadmap page",
            map: "Map",
            capabilities: "Capabilities",
            languageSwitchAria: "Switch language",
        },
        index: {
            skipToMain: "Skip to main content",
            mainAria: "Heritage map and assistant workspace",
            resizeAria: "Resize map and assistant panels",
        },
        capabilities: {
            status: "Product Status",
            title: "Current capabilities and near-term roadmap",
            description:
                "This page gives a transparent snapshot of what the app can do today, what is planned next, and which parts need focused engineering work before production rollout.",
            currentTitle: "Current capabilities",
            comingSoonTitle: "Coming soon",
            needsWorkTitle: "Needs working on",
            current: [
                "Interactive map with viewport-based loading and clustering.",
                "Search heritage sites by name and metadata with keyboard navigation.",
                "Site detail dialog with registry metadata and coordinates.",
                "Shareable URL state for current map area, zoom, and search term.",
            ],
            comingSoon: [
                "Automated risk scoring and classification for each heritage site.",
                "Risk driver breakdowns with explainable score components.",
                "Historical trend views and scenario-based projections.",
                "Workflow-ready AI assistant connected to live risk analysis.",
            ],
            needsWork: [
                "Risk model calibration and validation against real events.",
                "Expanded test coverage for map interactions and query-state sync.",
                "Production deployment hardening and monitoring dashboards.",
                "Role-based collaboration and export/reporting workflows.",
            ],
        },
        chat: {
            panelAria: "AI assistant panel",
            title: "AI Assistant",
            conversationAria: "Assistant conversation",
            userMessageAria: "User message",
            assistantMessageAria: "Assistant message",
            thinking: "Thinking...",
            inputLabel: "Ask the AI assistant about heritage risks",
            inputPlaceholder: "Ask about heritage risks...",
            sendMessageAria: "Send message",
            modelLabel: "Model",
            webSearchLabel: "Web search",
            webSearchHint: "Enable current web lookup through the Azure Responses API tool.",
            webSearchUsed: "Web search used",
            sourcesLabel: "Sources",
            resetConversationAria: "Reset conversation",
            notConfigured: "not configured",
            missingConfigPrefix: "Missing env configuration:",
            noModelsConfigured: "No chat models were returned by the backend.",
            noModelsAvailable: "The backend found chat models, but none are fully configured yet.",
            loadModelsFailed: "Unable to load chat model configuration.",
            requestFailed: "The assistant request failed. Please try again.",
            welcome:
                "Hello! I'm your KULTURKO assistant. Ask me about Slovenian cultural heritage sites, their risk levels, or environmental threats they face.",
        },
        map: {
            containerAria: "Heritage map and search",
            instructions:
                "Interactive map showing heritage sites and clusters. Use search results to navigate to a site and open details.",
            mapAria: "Interactive heritage map",
            search: {
                wrapperAria: "Heritage site search",
                inputLabel: "Search heritage sites",
                placeholder: "Search heritage sites...",
                clearAria: "Clear search input",
                chipsAria: "Recent and quick search terms",
                useChipAriaPrefix: "Use search term",
                resultsAria: "Search results",
                selectAriaPrefix: "Select",
                fallbackSubtitle: "Heritage site",
                searching: "Searching...",
                noResults: "No sites found",
            },
            overlay: {
                title: "Overlays",
                groupAria: "Hazard overlays",
                options: {
                    fire: "Fire",
                    flood: "Flood",
                    air: "Air",
                    landslide: "Landslide",
                },
                overlayAriaSuffix: "overlay",
                leastLabel: "Least endangered",
                mostLabel: "Most endangered",
                noneActive: "No overlay active",
                scaleSuffix: "scale",
                loading: "Loading overlay data...",
                viewRenderedSuffix: "rendered",
                sourceItemsInView: "source items in view",
                inViewSuffix: "in view",
                error: "Overlay data is temporarily unavailable.",
                units: {
                    areas: "areas",
                    cells: "cells",
                },
            },
            legend: {
                containerAria: "Map legend",
                title: "Map legend",
                singleSite: "Single heritage site",
                cluster: "Cluster (click to zoom in)",
                pointSummary: "map points representing",
                siteSummary: "heritage sites",
            },
            status: {
                retryNow: "Retry now",
                unableLoadData: "Unable to load heritage data.",
            },
            recovery: {
                retrying: "Retrying...",
                serverWakingWithProgress: "Server waking up. Loading heritage dataset",
                serverWaking: "Server waking up. Loading heritage dataset...",
                serverStartingRetrying: "Server is starting and dataset is not ready yet. Retrying automatically...",
                coldStartRetrying: "Server cold start in progress. Loading heritage data and retrying...",
                waitingBackendConnection: "Waiting for backend connection. Retrying automatically...",
                backendNotReady: "Backend not ready yet. Retrying automatically...",
                temporaryIssue: "Temporary server issue. Retrying automatically...",
                startupProgress: "Startup progress",
                lastUpdate: "Last update",
            },
        },
        siteDialog: {
            description: "Details for this cultural heritage site, including location and metadata from the registry.",
            type: "Type",
            municipality: "Municipality",
            protection: "Protection",
            coordinates: "Coordinates",
            loading: "Loading full site details...",
            additionalData: "Additional data",
        },
        notFound: {
            title: "Oops! Page not found",
            backHome: "Return to Home",
        },
    },
    sl: {
        header: {
            resetAppAria: "Ponastavi pogled aplikacije in počisti stanje URL-ja",
            navAria: "Glavna navigacija",
            openMapAria: "Odpri interaktivni zemljevid",
            openCapabilitiesAria: "Odpri stran z zmožnostmi in načrtom",
            map: "Zemljevid",
            capabilities: "Zmožnosti",
            languageSwitchAria: "Preklopi jezik",
        },
        index: {
            skipToMain: "Preskoči na glavno vsebino",
            mainAria: "Delovni prostor z zemljevidom dediščine in pomočnikom",
            resizeAria: "Spremeni velikost zemljevida in panela pomočnika",
        },
        capabilities: {
            status: "Stanje izdelka",
            title: "Trenutne zmožnosti in kratkoročni načrt",
            description:
                "Ta stran pregledno prikazuje, kaj aplikacija zmore danes, kaj sledi v naslednjih korakih in kateri deli potrebujejo še osredotočeno inženirsko delo pred produkcijo.",
            currentTitle: "Trenutne zmožnosti",
            comingSoonTitle: "Kmalu",
            needsWorkTitle: "Potrebno nadaljnje delo",
            current: [
                "Interaktivni zemljevid z nalaganjem glede na vidno območje in združevanjem točk.",
                "Iskanje enot dediščine po imenu in metapodatkih s tipkovno navigacijo.",
                "Pogovorno okno s podrobnostmi lokacije, registrskimi metapodatki in koordinatami.",
                "Deljivo stanje URL-ja za trenutno območje zemljevida, povečavo in iskalni niz.",
            ],
            comingSoon: [
                "Samodejno točkovanje tveganj in razvrščanje za vsako enoto dediščine.",
                "Razčlenitve dejavnikov tveganja z razložljivimi komponentami ocene.",
                "Pogledi zgodovinskih trendov in projekcije po scenarijih.",
                "AI pomočnik za delovne procese, povezan z analizo tveganj v živo.",
            ],
            needsWork: [
                "Kalibracija in validacija modela tveganja na podlagi realnih dogodkov.",
                "Razširjeno testno pokrivanje za interakcije zemljevida in sinhronizacijo stanja poizvedb.",
                "Utrditev produkcijskega okolja ter nadzorne plošče za spremljanje.",
                "Sodelovanje po vlogah ter izvozna in poročevalska opravila.",
            ],
        },
        chat: {
            panelAria: "Panel AI pomočnika",
            title: "AI pomočnik",
            conversationAria: "Pogovor s pomočnikom",
            userMessageAria: "Sporočilo uporabnika",
            assistantMessageAria: "Sporočilo pomočnika",
            thinking: "Razmišljam...",
            inputLabel: "Vprašajte AI pomočnika o tveganjih dediščine",
            inputPlaceholder: "Vprašajte o tveganjih dediščine...",
            sendMessageAria: "Pošlji sporočilo",
            modelLabel: "Model",
            webSearchLabel: "Spletno iskanje",
            webSearchHint: "Omogoči sprotno spletno iskanje prek Azure Responses API orodja.",
            webSearchUsed: "Uporabljeno spletno iskanje",
            sourcesLabel: "Viri",
            resetConversationAria: "Ponastavi pogovor",
            notConfigured: "ni nastavljen",
            missingConfigPrefix: "Manjkajoča env konfiguracija:",
            noModelsConfigured: "Backend ni vrnil nobenih modelov za klepet.",
            noModelsAvailable: "Backend je našel modele, vendar noben še ni popolnoma nastavljen.",
            loadModelsFailed: "Nastavitve modelov za klepet ni bilo mogoče naložiti.",
            requestFailed: "Poizvedba do pomočnika ni uspela. Poskusite znova.",
            welcome:
                "Pozdravljeni! Sem vaš pomočnik KULTURKO. Vprašajte me o slovenskih enotah kulturne dediščine, njihovih ravneh tveganja ali okoljskih grožnjah.",
        },
        map: {
            containerAria: "Zemljevid dediščine in iskanje",
            instructions:
                "Interaktivni zemljevid z enotami dediščine in gručami. Za premik na lokacijo in odprtje podrobnosti uporabite rezultate iskanja.",
            mapAria: "Interaktivni zemljevid dediščine",
            search: {
                wrapperAria: "Iskanje enot dediščine",
                inputLabel: "Išči enote dediščine",
                placeholder: "Išči enote dediščine...",
                clearAria: "Počisti iskalni vnos",
                chipsAria: "Nedavni in hitri iskalni izrazi",
                useChipAriaPrefix: "Uporabi iskalni izraz",
                resultsAria: "Rezultati iskanja",
                selectAriaPrefix: "Izberi",
                fallbackSubtitle: "Enota dediščine",
                searching: "Iščem...",
                noResults: "Ni najdenih lokacij",
            },
            overlay: {
                title: "Sloji",
                groupAria: "Sloji nevarnosti",
                options: {
                    fire: "Požar",
                    flood: "Poplava",
                    air: "Zrak",
                    landslide: "Plaz",
                },
                overlayAriaSuffix: "sloj",
                leastLabel: "Najmanj ogroženo",
                mostLabel: "Najbolj ogroženo",
                noneActive: "Ni aktivnega sloja",
                scaleSuffix: "lestvica",
                loading: "Nalaganje podatkov sloja...",
                viewRenderedSuffix: "izrisano",
                sourceItemsInView: "izvornih elementov v pogledu",
                inViewSuffix: "v pogledu",
                error: "Podatki sloja trenutno niso na voljo.",
                units: {
                    areas: "območij",
                    cells: "celic",
                },
            },
            legend: {
                containerAria: "Legenda",
                title: "Legenda",
                singleSite: "Posamezna enota dediščine",
                cluster: "Gruča (klik za povečavo)",
                pointSummary: "točk na zemljevidu predstavlja",
                siteSummary: "enot kulturne dediščine",
            },
            status: {
                retryNow: "Poskusi znova",
                unableLoadData: "Podatkov dediščine ni mogoče naložiti.",
            },
            recovery: {
                retrying: "Ponovni poskus...",
                serverWakingWithProgress: "Strežnik se zaganja. Nalagam podatke dediščine",
                serverWaking: "Strežnik se zaganja. Nalagam podatke dediščine...",
                serverStartingRetrying:
                    "Strežnik se zaganja in podatki še niso pripravljeni. Samodejni ponovni poskus...",
                coldStartRetrying: "Hladen zagon strežnika je v teku. Nalagam podatke dediščine in ponavljam poskus...",
                waitingBackendConnection: "Čakam na povezavo z backendom. Samodejni ponovni poskus...",
                backendNotReady: "Backend še ni pripravljen. Samodejni ponovni poskus...",
                temporaryIssue: "Začasna težava strežnika. Samodejni ponovni poskus...",
                startupProgress: "Napredek zagona",
                lastUpdate: "Zadnja posodobitev",
            },
        },
        siteDialog: {
            description: "Podrobnosti za to enoto kulturne dediščine, vključno z lokacijo in metapodatki iz registra.",
            type: "Tip",
            municipality: "Občina",
            protection: "Varstvo",
            coordinates: "Koordinate",
            loading: "Nalaganje celotnih podrobnosti lokacije...",
            additionalData: "Dodatni podatki",
        },
        notFound: {
            title: "Ups! Stran ni bila najdena",
            backHome: "Nazaj na začetno stran",
        },
    },
} as const;

type WidenLiterals<T> = T extends string
    ? string
    : T extends readonly (infer U)[]
      ? readonly WidenLiterals<U>[]
      : T extends object
        ? { readonly [K in keyof T]: WidenLiterals<T[K]> }
        : T;

type MessageBundle = WidenLiterals<(typeof messages)["en"]>;

interface LanguageContextValue {
    language: Language;
    setLanguage: (next: Language) => void;
    m: MessageBundle;
}

const defaultContext: LanguageContextValue = {
    language: "en",
    setLanguage: () => {
        // No-op fallback for isolated component tests without provider.
    },
    m: messages.en,
};

const LanguageContext = createContext<LanguageContextValue>(defaultContext);

function readStoredLanguage(): Language {
    if (typeof window === "undefined") return "sl";
    const stored = window.localStorage.getItem(LANGUAGE_STORAGE_KEY);
    return stored === "en" || stored === "sl" ? stored : "sl";
}

export function LanguageProvider({ children }: { children: ReactNode }) {
    const [language, setLanguageState] = useState<Language>(() => readStoredLanguage());

    useEffect(() => {
        if (typeof window === "undefined") return;
        window.localStorage.setItem(LANGUAGE_STORAGE_KEY, language);
        document.documentElement.lang = language;
    }, [language]);

    const setLanguage = (next: Language) => {
        setLanguageState(next);
    };

    const value = useMemo(
        () => ({
            language,
            setLanguage,
            m: messages[language],
        }),
        [language],
    );

    return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useLanguage() {
    return useContext(LanguageContext);
}
