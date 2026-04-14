export interface HeritageSiteBase {
	id: string;
	registryId?: string;
	name: string;
	lat: number;
	lng: number;
	type?: string;
	protectionStatus?: string;
	municipality?: string;
}

export interface HeritageSiteSummary extends HeritageSiteBase {
	isCluster?: boolean;
	clusterCount?: number;
}

export interface HeritageSiteDetail extends HeritageSiteBase {
	isCluster?: boolean;
	description?: string;
	dating?: string;
	locationDescription?: string;
	photoUrl?: string;
	fireHazard?: number;
	floodHazard?: number;
	landslideHazard?: number;
	earthquakeHazard?: number;
	fireHazardOriginal?: number;
	floodHazardOriginal?: number;
	landslideHazardOriginal?: number;
	earthquakeHazardOriginal?: number;
}

export interface HeritageSiteListResponse {
	items: HeritageSiteSummary[];
	total: number;
	sourceCount: number;
}
