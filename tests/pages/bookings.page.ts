import { Page, Locator } from '@playwright/test';

export class BookingPage {
  readonly page: Page;
  readonly searchInput: Locator;
  readonly statusFilter: Locator;
  readonly rows: Locator;
  readonly statusBadges: Locator;
  readonly pageInfo: Locator;
  readonly emptyState: Locator;
  readonly loading: Locator;

  constructor(page: Page) {
    this.page = page;
    this.searchInput = page.getByLabel('Search AWB or commodity');
    this.statusFilter = page.getByLabel('Status');
    this.rows = page.getByTestId('booking-row');
    this.statusBadges = page.getByTestId('status-badge');
    this.pageInfo = page.getByTestId('page-info');
    this.emptyState = page.getByTestId('empty-state');
    this.loading = page.getByTestId('loading');
  }

  async goto() {
    await this.page.goto('/bookings');
    await this.waitForLoaded();
  }

  async waitForLoaded() {
    await this.loading.waitFor({ state: 'hidden' });
  }

  async search(text: string) {
    const response = this.page.waitForResponse((res) => {
      const url = new URL(res.url());
      return url.pathname === '/api/bookings' && url.searchParams.get('search') === text;
    });    
    await this.searchInput.fill(text);
    await response;
    await this.waitForLoaded();
  }

  async filterByStatus(label: string) {
    const response = this.page.waitForResponse((res) => {
      const url = new URL(res.url());
      return url.pathname === '/api/bookings' && url.searchParams.has('status');
    });
    await this.statusFilter.selectOption({ label });
    await response;
    await this.waitForLoaded();
  }
}