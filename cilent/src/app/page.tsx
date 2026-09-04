"use client";

import { useEffect, useState } from "react";

const DEFAULT_TARGET_PRODUCT = "Singing Bowls";

type Buyer = {
  buyer_id?: number;
  company_name: string;
  page_title?: string;
  website: string;
  emails?: string[];
  phones?: string[];
  classification: string;
  confidence: number;
  reason?: string;
  source?: string;
  source_url?: string;
  search_query?: string;
  buyer_contact_emails?: string[];
  email_available?: boolean;
  database_saved?: boolean;
  outreach_status?: string;
};

type StoredBuyer = Buyer & {
  id: number;
  target_product?: string;
};

type DiscoveryResponse = {
  success: boolean;
  target_product: string;
  total_candidates_found: number;
  business_candidates_found: number;
  intent_candidates_found: number;
  reviewed_candidates: unknown[];
  unreachable_candidates: unknown[];
  buyers: Buyer[];
};

export default function Home() {
  const [targetProduct, setTargetProduct] = useState(DEFAULT_TARGET_PRODUCT);
  const [numResults, setNumResults] = useState(10);

  const [data, setData] = useState<DiscoveryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [sendingBuyerId, setSendingBuyerId] = useState<number | null>(null);
  const [sendErrors, setSendErrors] = useState<Record<number, string>>({});

  useEffect(() => {
    async function loadSavedBuyers() {
      setLoading(true);

      try {
        const response = await fetch("http://localhost:8000/api/buyers");

        if (!response.ok) {
          const errorData = await response.json().catch(() => null);
          throw new Error(errorData?.detail || "Saved buyers could not be loaded.");
        }

        const result: { buyers: StoredBuyer[] } = await response.json();
        const savedBuyers = result.buyers.map((buyer) => ({
          ...buyer,
          buyer_id: buyer.id,
          database_saved: true,
          email_available: (buyer.emails ?? []).length > 0,
        }));

        setData({
          success: true,
          target_product:
            savedBuyers[0]?.target_product ?? DEFAULT_TARGET_PRODUCT,
          total_candidates_found: savedBuyers.length,
          business_candidates_found: savedBuyers.length,
          intent_candidates_found: 0,
          reviewed_candidates: [],
          unreachable_candidates: [],
          buyers: savedBuyers,
        });
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "Saved buyers could not be loaded."
        );
      } finally {
        setLoading(false);
      }
    }

    loadSavedBuyers();
  }, []);

  async function discoverBuyers() {
    setLoading(true);
    setError("");
    setData(null);

    try {
      const params = new URLSearchParams({
        target_product: targetProduct,
        num_results: String(numResults),
      });

      const response = await fetch(
        `http://localhost:8000/api/buyers/discover?${params.toString()}`,
        {
          method: "POST",
        }
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => null);

        throw new Error(
          errorData?.detail || "Buyer discovery request failed"
        );
      }

      const result: DiscoveryResponse = await response.json();

      setData(result);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Something went wrong while discovering buyers."
      );
    } finally {
      setLoading(false);
    }
  }

  async function sendEmail(buyer: Buyer) {
    if (!buyer.buyer_id) {
      return;
    }

    setSendingBuyerId(buyer.buyer_id);
    setSendErrors((current) => {
      const next = { ...current };
      delete next[buyer.buyer_id as number];
      return next;
    });

    try {
      const response = await fetch(
        "http://localhost:8000/api/outreach/send-gmail",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            buyer_id: buyer.buyer_id,
            force: false,
          }),
        }
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        throw new Error(errorData?.detail || "Email could not be sent.");
      }

      setData((current) =>
        current
          ? {
              ...current,
              buyers: current.buyers.map((currentBuyer) =>
                currentBuyer.buyer_id === buyer.buyer_id
                  ? { ...currentBuyer, outreach_status: "SENT" }
                  : currentBuyer
              ),
            }
          : current
      );
    } catch (err) {
      setSendErrors((current) => ({
        ...current,
        [buyer.buyer_id as number]:
          err instanceof Error ? err.message : "Email could not be sent.",
      }));
    } finally {
      setSendingBuyerId(null);
    }
  }

  const buyers = data?.buyers ?? [];

  const emailCount = buyers.filter(
    (buyer) =>
      buyer.email_available ||
      (buyer.emails && buyer.emails.length > 0) ||
      (buyer.buyer_contact_emails &&
        buyer.buyer_contact_emails.length > 0)
  ).length;

  return (
    <main className="min-h-screen bg-slate-50">
      {/* Header */}
      <header className="border-b bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-5">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              EXPORT Automation
            </h1>

            <p className="mt-1 text-sm text-slate-500">
              AI-powered buyer discovery platform
            </p>
          </div>

          <div className="flex items-center gap-2 rounded-full border bg-slate-50 px-4 py-2">
            <span
              className={`h-2.5 w-2.5 rounded-full ${
                loading ? "bg-amber-500" : "bg-green-500"
              }`}
            />

            <span className="text-sm font-medium text-slate-700">
              {loading ? "Searching..." : "Ready"}
            </span>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-7xl px-6 py-8">
        {/* Search Section */}
        <section className="rounded-2xl border bg-white p-6 shadow-sm">
          <div className="mb-6">
            <h2 className="text-lg font-semibold text-slate-900">
              Find Potential Buyers
            </h2>

            <p className="mt-1 text-sm text-slate-500">
              Search the web for businesses showing potential purchasing
              intent for your target product.
            </p>
          </div>

          <div className="grid gap-4 md:grid-cols-[1fr_180px_auto]">
            {/* Product */}
            <div>
              <label className="mb-2 block text-sm font-medium text-slate-700">
                Target Product
              </label>

              <input
                type="text"
                value={targetProduct}
                onChange={(e) => setTargetProduct(e.target.value)}
                placeholder="e.g. Singing Bowls"
                className="w-full rounded-lg border border-slate-300 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-slate-500 focus:ring-2 focus:ring-slate-200"
              />
            </div>

            {/* Number of results */}
            <div>
              <label className="mb-2 block text-sm font-medium text-slate-700">
                Results / Query
              </label>

              <input
                type="number"
                min={1}
                max={20}
                value={numResults}
                onChange={(e) =>
                  setNumResults(Number(e.target.value))
                }
                className="w-full rounded-lg border border-slate-300 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-slate-500 focus:ring-2 focus:ring-slate-200"
              />
            </div>

            {/* Button */}
            <div className="flex items-end">
              <button
                onClick={discoverBuyers}
                disabled={loading || !targetProduct.trim()}
                className="w-full rounded-lg bg-slate-900 px-6 py-3 text-sm font-semibold text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-50 md:w-auto"
              >
                {loading ? "Discovering..." : "Find Buyers"}
              </button>
            </div>
          </div>

          {/* Error */}
          {error && (
            <div className="mt-5 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              <strong>Error:</strong> {error}
            </div>
          )}
        </section>

        {/* Summary Cards */}
        {data && (
          <section className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <SummaryCard
              title="Candidates"
              value={data.total_candidates_found}
              description="Discovered"
            />

            <SummaryCard
              title="Confirmed Buyers"
              value={buyers.length}
              description="Qualified"
            />

            <SummaryCard
              title="Emails Available"
              value={emailCount}
              description="Public contact info"
            />

            <SummaryCard
              title="Unreachable"
              value={data.unreachable_candidates.length}
              description="Could not be reviewed"
            />
          </section>
        )}

        {/* Results */}
        {data && (
          <section className="mt-6 rounded-2xl border bg-white shadow-sm">
            <div className="flex flex-col gap-2 border-b px-6 py-5 md:flex-row md:items-center md:justify-between">
              <div>
                <h2 className="font-semibold text-slate-900">
                  Confirmed Buyers
                </h2>

                <p className="text-sm text-slate-500">
                  Target product: {data.target_product}
                </p>
              </div>

              <div className="text-sm text-slate-500">
                {buyers.length} buyer{buyers.length !== 1 ? "s" : ""}
              </div>
            </div>

            {buyers.length === 0 ? (
              <div className="px-6 py-16 text-center">
                <div className="text-lg font-semibold text-slate-800">
                  No confirmed buyers found
                </div>

                <p className="mt-2 text-sm text-slate-500">
                  Try another product or increase the number of results.
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[1000px] text-left">
                  <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                    <tr>
                      <th className="px-6 py-4">Company</th>
                      <th className="px-6 py-4">Website</th>
                      <th className="px-6 py-4">Confidence</th>
                      <th className="px-6 py-4">Email</th>
                      <th className="px-6 py-4">Phone</th>
                      <th className="px-6 py-4">Database</th>
                      <th className="px-6 py-4">Outreach</th>
                    </tr>
                  </thead>

                  <tbody className="divide-y">
                    {buyers.map((buyer, index) => {
                      const emails = [
                        ...(buyer.emails ?? []),
                        ...(buyer.buyer_contact_emails ?? []),
                      ];

                      const uniqueEmails = [
                        ...new Set(emails),
                      ];

                      const phones = buyer.phones ?? [];

                      return (
                        <tr
                          key={`${buyer.website}-${index}`}
                          className="transition hover:bg-slate-50"
                        >
                          {/* Company */}
                          <td className="px-6 py-5 align-top">
                            <div className="font-semibold text-slate-900">
                              {buyer.company_name}
                            </div>

                            {buyer.reason && (
                              <div className="mt-1 max-w-sm text-xs leading-5 text-slate-500">
                                {buyer.reason}
                              </div>
                            )}
                          </td>

                          {/* Website */}
                          <td className="px-6 py-5 align-top">
                            <a
                              href={buyer.website}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-sm font-medium text-blue-600 hover:underline"
                            >
                              Visit website
                            </a>
                          </td>

                          {/* Confidence */}
                          <td className="px-6 py-5 align-top">
                            <span className="inline-flex rounded-full bg-green-100 px-3 py-1 text-xs font-semibold text-green-700">
                              {formatConfidence(buyer.confidence)}
                            </span>
                          </td>

                          {/* Email */}
                          <td className="px-6 py-5 align-top">
                            {uniqueEmails.length > 0 ? (
                              <div className="space-y-1">
                                {uniqueEmails.map((email) => (
                                  <a
                                    key={email}
                                    href={`mailto:${email}`}
                                    className="block text-sm text-blue-600 hover:underline"
                                  >
                                    {email}
                                  </a>
                                ))}
                              </div>
                            ) : (
                              <span className="text-sm text-slate-400">
                                Not available
                              </span>
                            )}
                          </td>

                          {/* Phone */}
                          <td className="px-6 py-5 align-top">
                            {phones.length > 0 ? (
                              <div className="space-y-1">
                                {phones.map((phone) => (
                                  <div
                                    key={phone}
                                    className="text-sm text-slate-700"
                                  >
                                    {phone}
                                  </div>
                                ))}
                              </div>
                            ) : (
                              <span className="text-sm text-slate-400">
                                Not available
                              </span>
                            )}
                          </td>

                          {/* Database */}
                          <td className="px-6 py-5 align-top">
                            {buyer.database_saved ? (
                              <span className="inline-flex rounded-full bg-green-100 px-3 py-1 text-xs font-semibold text-green-700">
                                Saved
                              </span>
                            ) : (
                              <span className="inline-flex rounded-full bg-red-100 px-3 py-1 text-xs font-semibold text-red-700">
                                Not saved
                              </span>
                            )}
                          </td>

                          {/* Outreach */}
                          <td className="px-6 py-5 align-top">
                            {buyer.outreach_status === "SENT" ? (
                              <span className="inline-flex rounded-full bg-green-100 px-3 py-1 text-xs font-semibold text-green-700">
                                Sent
                              </span>
                            ) : buyer.buyer_id ? (
                              <>
                                <button
                                  type="button"
                                  onClick={() => sendEmail(buyer)}
                                  disabled={
                                    sendingBuyerId === buyer.buyer_id ||
                                    !uniqueEmails.length
                                  }
                                  className="rounded-lg bg-slate-900 px-3 py-2 text-xs font-semibold text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
                                >
                                  {sendingBuyerId === buyer.buyer_id
                                    ? "Sending..."
                                    : "Send email"}
                                </button>

                                {sendErrors[buyer.buyer_id] && (
                                  <div className="mt-2 max-w-xs text-xs text-red-600">
                                    {sendErrors[buyer.buyer_id]}
                                  </div>
                                )}
                              </>
                            ) : (
                              <span className="text-xs text-slate-400">
                                Not available
                              </span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        )}

        {/* Initial State */}
        {!data && !loading && !error && (
          <section className="mt-6 rounded-2xl border border-dashed bg-white px-6 py-20 text-center">
            <h2 className="text-lg font-semibold text-slate-800">
              Ready to discover buyers
            </h2>

            <p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-slate-500">
              Enter a target product above and click{" "}
              <strong>Find Buyers</strong>. The backend will search,
              validate, classify and save confirmed buyers to PostgreSQL.
            </p>
          </section>
        )}
      </div>
    </main>
  );
}

function SummaryCard({
  title,
  value,
  description,
}: {
  title: string;
  value: number;
  description: string;
}) {
  return (
    <div className="rounded-2xl border bg-white p-5 shadow-sm">
      <div className="text-sm font-medium text-slate-500">
        {title}
      </div>

      <div className="mt-2 text-3xl font-bold text-slate-900">
        {value}
      </div>

      <div className="mt-1 text-xs text-slate-400">
        {description}
      </div>
    </div>
  );
}

function formatConfidence(confidence: number) {
  if (confidence <= 1) {
    return `${Math.round(confidence * 100)}%`;
  }

  return `${Math.round(confidence)}%`;
}