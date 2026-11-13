// Mesmos contratos do site (frontend/src/api/types.ts), reduzidos ao que o app usa.
export interface User { id: number; email: string; full_name: string; cpf: string; is_member: boolean; marketing_opt_in: boolean }
export interface Tag { code: string; name: string; kind: string }
export interface SKU { id: number; code: string; variant_name: string; price_cents: number | null; list_price_cents: number | null; available: number; sellable: boolean; contains: Tag[] }
export interface ProductSummary { id: number; slug: string; name: string; category: { slug: string; name: string }; from_price_cents: number | null; from_list_price_cents: number | null; sellable: boolean; is_recurring_food: boolean }
export interface Product extends ProductSummary { description: string; conservation: string; skus: SKU[] }
export interface Plan {
  code: string; name: string; tagline: string; description: string; highlight: boolean; available: boolean;
  offer: { id: number; version: number; price_cents: number; shipping_cents: number; commitment_options: number[]; terms: string } | null;
  composition: { lines: { category: string; category_name: string; quantity: number }[]; total_items: number } | null;
}
export interface Address { id: number; label: string; street: string; number: string; city: string; state: string; cep: string; is_default: boolean }
export interface Dog { id: number; name: string; size: string; weight_kg: string | null; is_active: boolean; missing_fields: string[]; restrictions_detail: Tag[] }
export interface Payment { id: number; external_id: string; billing_type: string; status: string; status_label: string; is_paid: boolean; value_cents: number; due_date: string | null; invoice_url: string; bank_slip_url: string; pix_payload: string; reference: string }
export interface Quote { lines: { sku_id: number; name: string; quantity: number; unit_price_cents: number; total_cents: number }[]; subtotal_cents: number; discount_cents: number; shipping_cents: number; total_cents: number; eta_days: number | null; problems: string[]; can_checkout: boolean }
export interface Order { id: number; number: string; status: string; status_label: string; total_cents: number; payment: Payment | null; created_at: string }
export interface Subscription { id: number; number: string; kind: string; status: string; status_label: string; plan_name: string | null; dog_name: string | null; sku_name: string | null; total_per_cycle_cents: number; next_billing_date: string | null; next_cutoff_date: string | null; cancel_effective_date: string | null; pending_payment: Payment | null }
export interface Delivery { id: number; number: string; kind_label: string; status: string; status_label: string; reference: string; content_status: string; tracking_code: string; can_review: boolean; lines: { id: number; product_name: string; quantity: number; dog_name: string | null; review: { rating: number } | null }[] }
