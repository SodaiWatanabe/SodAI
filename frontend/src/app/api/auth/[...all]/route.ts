import { proxyAuthRequest } from "@/lib/auth/proxy";
import { getAuthServiceUrl } from "@/lib/auth/service-url";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

function handleAuthRequest(request: Request): Promise<Response> {
  return proxyAuthRequest(request, { serviceUrl: getAuthServiceUrl() });
}

export { handleAuthRequest as GET, handleAuthRequest as POST };
