/**
 * X402 Protocol Middleware
 * Core implementation of the HTTP 402 Payment Required flow.
 * Migrated to Supabase (PostgreSQL).
 */
import { v4 as uuidv4 } from 'uuid';
import { verifyAlgorandPayment, getProviderWallet } from '../lib/algorand.js';
import { db } from '../lib/database.js';

const DEFAULT_PRICE = 0.001;

// Default prices for known endpoints (used when Supabase is unavailable)
const ENDPOINT_PRICES = {
  '/api/translate': 0.001,
  '/api/summarize': 0.002,
  '/api/sentiment': 0.001,
  '/api/image/generate': 0.005,
};

async function getEndpointPrice(path) {
  const cleanPath = path.split('?')[0];
  
  // First check hardcoded prices (instant, no DB needed)
  if (ENDPOINT_PRICES[cleanPath]) return ENDPOINT_PRICES[cleanPath];

  // Try DB with a 3-second timeout so we never hang
  try {
    const dbLookup = db
      .from('api_registry')
      .select('price')
      .eq('endpoint', cleanPath)
      .eq('is_active', true)
      .maybeSingle();

    const timeout = new Promise((_, reject) => setTimeout(() => reject(new Error('timeout')), 3000));
    const { data: row, error } = await Promise.race([dbLookup, timeout]);
    
    if (row && !error) return row.price;
  } catch (e) {
    console.warn('[X402 Price] Using default price for', cleanPath);
  }
  return DEFAULT_PRICE;
}

/**
 * X402 Middleware
 */
export async function x402Middleware(req, res, next) {
  const endpoint = req.path ? `/api${req.path}` : req.url;
  const cleanEndpoint = endpoint.split('?')[0];

  // Skip payment for docs/health/info endpoints and the Gemma agent router (free routing helper)
  const skipPaths = ['/api/docs', '/api/redoc', '/api/openapi.json', '/api/health', '/api/agent'];
  if (skipPaths.some(p => cleanEndpoint.startsWith(p))) {
    return next();
  }

  const price = await getEndpointPrice(cleanEndpoint);
  const paymentHeader = req.headers['x-payment'] || req.headers['X-Payment'];
  const requestId = uuidv4().slice(0, 8);

  // ── No payment header → return 402 ───────────────────────────────────────
  if (!paymentHeader) {
    const provider = getProviderWallet();
    const response = {
      x402Version: 1,
      error: 'Payment Required',
      accepts: [
        {
          scheme: 'algorand',
          network: process.env.ALGORAND_NETWORK || 'testnet',
          amount: price.toString(),
          currency: 'ALGO',
          recipient: provider,
          memo: `${cleanEndpoint}:${requestId}`,
          description: `Pay-per-use: ${cleanEndpoint}`,
        },
      ],
      memo: `${cleanEndpoint}:${requestId}`,
      endpoint: cleanEndpoint,
      amount: price,
      currency: 'ALGO',
      instructions: {
        step1: `Send ${price} ALGO to ${provider} on Algorand testnet`,
        step2: `Get your transaction ID from the Algorand explorer`,
        step3: `Resend this request with header: X-Payment: txid:<YOUR_TX_ID>`,
      },
    };

    // Log 402 event to Supabase
    try {
      await db.from('transactions').insert([{
        id: requestId,
        endpoint: cleanEndpoint,
        amount: price,
        status: 'pending_payment'
      }]);
    } catch (e) { /* ignore */ }

    return res.status(402)
      .set('X-402-Version', '1')
      .set('Content-Type', 'application/json')
      .json(response);
  }

  // ── X-Payment header present → verify ────────────────────────────────────
  const parts = paymentHeader.trim().split(':');
  if (parts.length < 2 || parts[0].toLowerCase() !== 'txid') {
    return res.status(400).json({
      error: 'Invalid X-Payment format',
      expected: 'X-Payment: txid:<ALGORAND_TX_ID>',
      received: paymentHeader,
    });
  }

  const txId = parts.slice(1).join(':').trim();
  const provider = getProviderWallet();

  try {
    const verification = await verifyAlgorandPayment({
      txId,
      expectedAmount: price,
      recipient: provider,
      endpoint: cleanEndpoint,
    });

    if (!verification.verified) {
      // Log failed verification
      try {
        await db.from('transactions').insert([{
          id: requestId,
          endpoint: cleanEndpoint,
          amount: price,
          tx_id: txId,
          status: 'failed',
          error: verification.error
        }]);
      } catch (e) { /* ignore */ }

      return res.status(402).json({
        error: 'Payment Verification Failed',
        reason: verification.error,
        tx_id: txId,
        required_amount: price,
        currency: 'ALGO',
      });
    }

    // ✓ Payment verified — log completion in Supabase
    try {
      const today = new Date().toISOString().split('T')[0];

      await Promise.all([
        // Upsert transaction status
        db.from('transactions').upsert([{
          id: requestId,
          endpoint: cleanEndpoint,
          amount: price,
          tx_id: txId,
          sender: verification.sender || 'unknown',
          status: 'completed'
        }]),

        // Increment stats (manual logic because Supabase upsert doesn't math easy on non-PK fields)
        updateProviderStats(today, cleanEndpoint, price)
      ]);
    } catch (e) { 
      console.warn('[X402 Log Error]', e.message);
    }

    console.log(`[X402] ✓ Payment verified | tx=${txId} | endpoint=${cleanEndpoint} | amount=${price} ALGO`);

    req.headers['x-payment-verified'] = 'true';
    req.headers['x-payment-tx-id'] = txId;
    req.headers['x-payment-amount'] = price.toString();
    req.x402_sender = verification.sender;
    req.x402_amount = price;

    return next();

  } catch (err) {
    console.error('[X402] Verification error:', err);
    return res.status(500).json({
      error: 'Internal payment verification error',
      detail: err.message,
    });
  }
}

/**
 * Helper to update provider daily stats.
 * Uses a manual fetch-and-update since Postgres 'ON CONFLICT' 
 * is easier via custom RPC or upsert with increments in one go.
 */
async function updateProviderStats(date, endpoint, price) {
    const { data: existing } = await db
        .from('provider_stats')
        .select('*')
        .eq('date', date)
        .eq('endpoint', endpoint)
        .maybeSingle();

    if (existing) {
        await db.from('provider_stats')
            .update({
                requests: (existing.requests || 0) + 1,
                earnings: (existing.earnings || 0) + price
            })
            .eq('date', date)
            .eq('endpoint', endpoint);
    } else {
        await db.from('provider_stats').insert([{
            date, endpoint, requests: 1, earnings: price
        }]);
    }
}
