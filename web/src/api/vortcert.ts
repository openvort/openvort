import request from "@/utils/request";

// ============ Stats ============

export function getCertStats() {
    return request.get("/cert/stats");
}

// ============ DNS Providers ============

export function getCertDnsProviders() {
    return request.get("/cert/dns-providers");
}

export function createCertDnsProvider(data: {
    name: string;
    provider_type: string;
    api_key?: string;
    api_secret?: string;
    extra_config?: string;
}) {
    return request.post("/cert/dns-providers", data);
}

export function updateCertDnsProvider(id: string, data: {
    name?: string;
    provider_type?: string;
    api_key?: string;
    api_secret?: string;
    extra_config?: string;
}) {
    return request.put(`/cert/dns-providers/${id}`, data);
}

export function deleteCertDnsProvider(id: string) {
    return request.delete(`/cert/dns-providers/${id}`);
}

// ============ Domains ============

export function getCertDomains(params?: {
    keyword?: string;
    label?: string;
    status?: string;
    dns_provider_id?: string;
    page?: number;
    page_size?: number;
}) {
    return request.get("/cert/domains", { params });
}

export function createCertDomain(data: {
    domain: string;
    domain_type?: string;
    label?: string;
    note?: string;
    dns_provider_id?: string;
    responsible_member_id?: string;
}) {
    return request.post("/cert/domains", data);
}

export function updateCertDomain(id: string, data: {
    domain?: string;
    domain_type?: string;
    label?: string;
    note?: string;
    dns_provider_id?: string;
    responsible_member_id?: string;
}) {
    return request.put(`/cert/domains/${id}`, data);
}

export function deleteCertDomain(id: string) {
    return request.delete(`/cert/domains/${id}`);
}

export function importCertDomains(data: {
    domains: string[];
    label?: string;
    dns_provider_id?: string;
}) {
    return request.post("/cert/domains/import", data);
}

// ============ Certificate Check ============

export function checkAllDomains() {
    return request.post("/cert/check");
}

export function checkSingleDomain(domainId: string) {
    return request.post(`/cert/check/${domainId}`);
}

export function getCertCheckLogs(params?: {
    domain_id?: string;
    page?: number;
    page_size?: number;
}) {
    return request.get("/cert/check-logs", { params });
}

// ============ Certificates ============

export function getCertCertificates(params?: {
    domain_id?: string;
    status?: string;
    page?: number;
    page_size?: number;
}) {
    return request.get("/cert/certificates", { params });
}

export function getCertificateDetail(certId: string) {
    return request.get(`/cert/certificates/${certId}/detail`);
}

export function issueCertificate(data: {
    domain_id: string;
    wildcard?: boolean;
}) {
    return request.post("/cert/certificates/issue", data);
}

export function renewCertificate(certId: string) {
    return request.post(`/cert/certificates/${certId}/renew`);
}

export function deleteCertificate(certId: string) {
    return request.delete(`/cert/certificates/${certId}`);
}

export function downloadCertificate(certId: string) {
    return request.get(`/cert/certificates/${certId}/download`, {
        responseType: "blob",
    });
}

// ============ Deploy Targets ============

export function getCertDeployTargets() {
    return request.get("/cert/deploy-targets");
}

export function createCertDeployTarget(data: {
    name: string;
    target_type: string;
    config?: string;
    api_key?: string;
    dns_provider_id?: string;
}) {
    return request.post("/cert/deploy-targets", data);
}

export function updateCertDeployTarget(id: string, data: {
    name?: string;
    target_type?: string;
    config?: string;
    api_key?: string;
    dns_provider_id?: string;
}) {
    return request.put(`/cert/deploy-targets/${id}`, data);
}

export function deleteCertDeployTarget(id: string) {
    return request.delete(`/cert/deploy-targets/${id}`);
}

// ============ Deploy Action ============

export function deployCertificate(data: {
    certificate_id: string;
    target_ids: string[];
}) {
    return request.post("/cert/deploy", data);
}

export function getCertDeployLogs(params?: {
    certificate_id?: string;
    deploy_target_id?: string;
    domain?: string;
    page?: number;
    page_size?: number;
}) {
    return request.get("/cert/deploy-logs", { params });
}
