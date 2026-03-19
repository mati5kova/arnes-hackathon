export interface HeritageSiteSummary {
	id: string;
	registryId?: string;
	name: string;
	lat: number;
	lng: number;
	type?: string;
	protectionStatus?: string;
	municipality?: string;
	description?: string;
	isCluster?: boolean;
	clusterCount?: number;
}

export interface HeritageSiteField {
	label: string;
	value: string;
}

export interface HeritageSiteDetail extends HeritageSiteSummary {
	detailFields: HeritageSiteField[];
	sourceUrl: string;
}

export interface HeritageSiteListResponse {
	items: HeritageSiteSummary[];
	total: number;
	sourceCount: number;
	sourceUrl: string;
}
