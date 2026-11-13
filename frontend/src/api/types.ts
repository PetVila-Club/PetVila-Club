export interface Tag { id: number; code: string; name: string; kind: 'ingredient' | 'material' | 'feature' }
export interface Category { id: number; slug: string; name: string; description: string; is_kit_category: boolean }

export interface SKU {
  id: number; code: string; variant_name: string; unit_description: string;
  price_cents: number | null; list_price_cents: number | null; member_price_cents: number | null;
  net_weight_g: number | null; weight_g: number | null; available: number; sellable: boolean;
  contains: Tag[]; suitable_sizes: string[];
}

export interface StoreCategoryRef { slug: string; name: string; parent: { slug: string; name: string } | null }
export interface Department { slug: string; name: string; children: { slug: string; name: string }[] }

export interface ProductSummary {
  id: number; slug: string; name: string; short_description: string; category: Category; store_category: StoreCategoryRef | null; picture: string;
  is_recurring_food: boolean; is_originals: boolean; from_price_cents: number | null; from_list_price_cents: number | null; from_member_price_cents: number | null;
  sellable: boolean;
}
export interface Product extends ProductSummary { description: string; conservation: string; skus: SKU[] }

export interface Offer {
  id: number; version: number; price_cents: number; currency: string; billing_cycle: string; shipping_cents: number;
  commitment_options: number[]; benefits: string; terms: string;
}
export interface CompositionLine { category: string; category_name: string; quantity: number }
export interface Plan {
  id: number; code: string; name: string; tagline: string; description: string; base_item_count: number;
  highlight: boolean; extras: { title: string; copy: string }[]; offer: Offer | null;
  composition: { version: number; lines: CompositionLine[]; total_items: number } | null; available: boolean;
}

export interface User {
  id: number; email: string; full_name: string; cpf: string; phone: string; marketing_opt_in: boolean;
  marketing_opt_in_updated_at: string | null; terms_version: string; is_member: boolean; is_staff_panel: boolean;
}

export interface Address {
  id: number; label: string; recipient: string; cep: string; street: string; number: string; complement: string;
  district: string; city: string; state: string; is_default: boolean;
}

export interface Dog {
  id: number; name: string; birth_date: string | null; estimated_age_years: number | null; age_years: number | null;
  size: '' | 'pequeno' | 'medio' | 'grande'; weight_kg: string | null; breed: string; preferences: string[];
  restrictions: string[]; preferences_detail: Tag[]; restrictions_detail: Tag[]; notes: string; is_active: boolean;
  profile_version: number; missing_fields: string[];
}

export interface Payment {
  id: number; external_id: string; purpose: 'order' | 'subscription'; billing_type: string; status: string;
  status_label: string; is_paid: boolean; value_cents: number; refunded_cents: number; due_date: string | null;
  invoice_url: string; bank_slip_url: string; pix_payload: string; pix_qr_image: string; confirmed_at: string | null;
  reference: string; created_at: string;
}

export interface QuoteLine {
  sku_id: number; sku_code: string; name: string; quantity: number; list_price_cents: number; unit_price_cents: number;
  total_cents: number; available: number;
}
export interface Quote {
  lines: QuoteLine[]; member_pricing: boolean; subtotal_cents: number; discount_cents: number; shipping_cents: number;
  total_cents: number; eta_days: number | null; zone: string | null; problems: string[]; can_checkout: boolean;
}

export interface OrderLine {
  id: number; sku_code: string; product_name: string; variant_name: string; quantity: number; list_price_cents: number;
  unit_price_cents: number; total_cents: number;
}
export interface Order {
  id: number; number: string; status: string; status_label: string; subtotal_cents: number; discount_cents: number;
  shipping_cents: number; total_cents: number; member_pricing: boolean; shipping_address: Record<string, string>;
  eta_days: number | null; billing_type: string; lines: OrderLine[]; payment: Payment | null;
  shipments: { id: number; number: string; status: string; status_label: string; tracking_code: string; tracking_url: string }[];
  created_at: string; paid_at: string | null;
}

export interface Cycle {
  id: number; code: string; number: number; status: string; status_label: string; billing_date: string | null;
  cutoff_date: string | null; price_cents: number; shipping_cents: number; paid_at: string | null;
}
export interface Subscription {
  id: number; number: string; kind: 'kit' | 'food'; kind_label: string; status: string; status_label: string;
  plan_name: string | null; dog: number | null; dog_name: string | null; sku_name: string | null; quantity: number;
  frequency_days: number; commitment_months: number | null; price_cents: number; shipping_cents: number;
  total_per_cycle_cents: number; billing_type: string; shipping_address: Record<string, string>; started_at: string | null;
  next_billing_date: string | null; next_cutoff_date: string | null; cancel_requested_at: string | null;
  cancel_effective_date: string | null; cycles: Cycle[]; pending_payment: Payment | null; created_at: string;
}

export interface DeliveryLine {
  id: number; sku_code: string; product_name: string; quantity: number; dog: number | null; dog_name: string | null;
  replaced_sku: { sku_code: string; product_name: string; justification: string } | null;
  review: { id: number; rating: number; comment: string; dog_reaction: string; allow_public: boolean } | null;
}
export interface Delivery {
  id: number; number: string; kind: string; kind_label: string; status: string; status_label: string; reference: string;
  content_status: 'previsto' | 'confirmado'; carrier: string; tracking_code: string; tracking_url: string;
  shipped_at: string | null; delivered_at: string | null; lines: DeliveryLine[]; can_review: boolean; created_at: string;
}

export interface Ticket {
  id: number; protocol: string; kind: string; kind_label: string; status: string; status_label: string; subject: string;
  description: string; reference: string; due_at: string | null; resolution: string; resolved_at: string | null;
  messages: { id: number; body: string; from_team: boolean; created_at: string }[]; created_at: string;
}
