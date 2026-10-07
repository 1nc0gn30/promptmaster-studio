# Handoff Sheet: Boise, ID Trade Storefronts

**City Desk · Neal Frazier Tech (@1nc0gn30)**  
**Target City**: Boise, ID (Ada County & Treasure Valley)  
**Standard**: One studio, one trade, one city per page. A set price. No invented reviews, no competitor counts, and no ranking promise. The owner already does the work.

---

## 1. Overview & Verification Summary

This handoff sheet covers the three active City Desk trade storefronts in Boise, ID:
1. **HVAC Shops** (`/cities/boise-id/hvac/`) — **$1,100**
2. **Plumbers** (`/cities/boise-id/plumbers/`) — **$900**
3. **Painters** (`/cities/boise-id/painters/`) — **$800**

Each storefront is served client-side via the City Desk mount (`/desk/cities/boise-id/...`) with strict schema markup, crawler-ready directives, zero console errors, and verified responsive layouts across mobile (375px), tablet (768px), and desktop (1440px).

---

## 2. Storefront Specifications & Deliverables

### A. HVAC Shops in Boise, ID
- **Mount Path**: `/desk/cities/boise-id/hvac/`
- **Catalog ID**: `offer_cities_boise_id_hvac`
- **Set Price**: **$1,100**
- **Headline**: HVAC shops in Boise: one page, one next step
- **Lede**: Owners lose jobs to whoever answers clearly. One page with a tune-up offer and a repair path, written for this city. The first screen names Boise, ID.
- **What Goes on the Page**:
  - Tune-up and repair split
  - A plain note on what a visit includes (filters, inspection, airflow check)
  - An answer block for filters and service windows
  - The handoff sheet
- **Schema.org**: `Service` entity typed for "One-page website for an HVAC owner" in Boise, ID ($1,100 USD offer).
- **Handoff Process**: The owner supplies seasonal tune-up rates and emergency diagnostic windows. City Desk replaces the placeholder facts with the owner's exact wording. The owner keeps the page and the domain.

---

### B. Plumbers in Boise, ID
- **Mount Path**: `/desk/cities/boise-id/plumbers/`
- **Catalog ID**: `offer_cities_boise_id_plumbers`
- **Set Price**: **$900**
- **Headline**: A page for a plumbing owner in Boise
- **Lede**: A leaking pipe does not wait for a brochure. One page that separates emergency work from scheduled work, with the city named. The first screen names Boise, ID.
- **What Goes on the Page**:
  - Emergency and scheduled dispatch paths
  - Water heater, drains, and fixtures called out
  - An answer block for arrival windows across Ada County
  - The handoff sheet
- **Schema.org**: `Service` entity typed for "One-page website for a plumbing owner" in Boise, ID ($900 USD offer).
- **Handoff Process**: The owner provides emergency dispatch hours and service truck dispatch terms. The page is handed off with zero ongoing retainers.

---

### C. Painters in Boise, ID
- **Mount Path**: `/desk/cities/boise-id/painters/`
- **Catalog ID**: `offer_cities_boise_id_painters`
- **Set Price**: **$800**
- **Headline**: What a painting owner in Boise can send
- **Lede**: The bid is already won or lost before the walkthrough. One page with the rooms you paint, a plain price range, and a way to ask for a walkthrough. The first screen names Boise, ID.
- **What Goes on the Page**:
  - Interior and exterior work split
  - Service area named in the first screen (Boise, Meridian, Eagle)
  - A short answer block for "how long will this take"
  - The handoff sheet
- **Schema.org**: `Service` entity typed for "One-page website for a painting owner" in Boise, ID ($800 USD offer).
- **Handoff Process**: The owner provides typical room pricing, exterior prep guidelines, and booking deposit rules.

---

## 3. Production Guardrail Verification

All three Boise pages satisfy the strict production baseline:
- **AEO / SEO**: Valid `<script type="application/ld+json">` declaring `Service` / `CollectionPage` schema with `areaServed: Boise, ID`.
- **Crawlers**: `robots.txt` explicitly allows crawlers with zero delay; `sitemap.xml` includes all Boise trade paths.
- **Viewport Hygiene**:
  - Mobile (375px): 0 horizontal scroll overflow (`scrollWidth <= clientWidth`), min 44px tap targets.
  - Tablet (768px): Balanced 2-column grid, fluid typography.
  - Desktop (1440px): 3-column Bento grid with crisp contrast (`#1c1915` on `#f3efe6`).
- **Integrity**: 0 unclosed tags, 0 console errors, 0 fake claims.

---

## 4. Owner Handoff Checklist

When an owner claims their Boise trade page:
1. [ ] Confirm business legal name, contact phone number, and license number.
2. [ ] Replace sample pricing with owner's exact schedule of fees.
3. [ ] Configure owner's direct receiving phone / form endpoint.
4. [ ] Point custom domain DNS records (or host statically under client's hosting).
5. [ ] Deliver static bundle and transfer full code ownership.
