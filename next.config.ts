import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    remotePatterns: [{ hostname: "img.youtube.com" }],
  },
  // The floating bottom-corner badge some viewers see isn't from this app's own code — it's most
  // likely Vercel's account-holder-only Toolbar (only visible when logged into the owning
  // account in the same browser, not to real visitors) rather than anything shipped here. This
  // just rules out Next's own dev-mode indicator as a possible source.
  devIndicators: false,
};

export default nextConfig;
