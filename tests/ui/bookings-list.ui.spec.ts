import { test, expect } from '@playwright/test';
import { BookingPage } from '../pages/bookings.page';
import { LoginPage } from '../pages/login.page';

test.describe('Booking list', () => {
    let bookingPage: BookingPage

    test.beforeEach( async ({ page }) =>  {
        const loginPage = new LoginPage(page);
        await loginPage.goto();
        await loginPage.login('acme', 'Acme@123');

        await expect(page).toHaveURL(/\/bookings$/);

        bookingPage = new BookingPage(page);
        await bookingPage.waitForLoaded();
    })

    test("First page shows 10 rows", async () => {
        await expect(bookingPage.rows).toHaveCount(10);
        await expect(bookingPage.pageInfo).toContainText('Page 1 of ');
    });

    test("Filter records with status as Delivered", async () => {
        await bookingPage.filterByStatus('Delivered');
        await expect(bookingPage.rows.first()).toBeVisible();
        await expect(bookingPage.statusBadges.filter( {hasNotText: 'Delivered'} )).toHaveCount(0);
    });

    test('random search, should return 0 results', async () => {
        await bookingPage.search('ZZZZ');
        await expect(bookingPage.rows).toHaveCount(0);
        await expect(bookingPage.emptyState).toBeVisible();
    });

    test('Filter records based on search word', async () => {
        await bookingPage.search('auto');
        
        await expect(bookingPage.rows.first()).toBeVisible();
        await expect(bookingPage.rows.filter ( {hasNotText: 'auto'} )).toHaveCount(0);
    });
})