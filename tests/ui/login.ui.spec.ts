import { test, expect } from '@playwright/test';
import { LoginPage } from '../pages/login.page';


test.describe('Login tests', () => {

    test('customer login lands on bookings', async ({ page }) => {
    const loginPage = new LoginPage(page);
    await loginPage.goto();
    await loginPage.login('acme', 'Acme@123');

    await expect(page).toHaveURL(/\/bookings$/);
    await expect(page.getByTestId('current-user')).toHaveText('Acme Freight Forwarders');
    });


    test('admin login lands on admin', async ({ page }) => {
    const loginPage = new LoginPage(page);
    await loginPage.goto();
    await loginPage.login('admin', 'Admin@123');

    await expect(page).toHaveURL(/\/admin$/);
    await expect(page.getByTestId('current-user')).toHaveText('Cargo Ops Admin');
    });


    test('wrong password error and stays on login', async ({ page }) => {
    const loginPage = new LoginPage(page);
    await loginPage.goto();
    await loginPage.login('admin', 'Acme@123');

    await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByRole('alert')).toHaveText('Invalid username or password');
    });


    test('reject accessing booking without logged in', async ({ page }) => {  
    await page.goto('/bookings/1');
    
    await expect(page).toHaveURL(/\/login$/);
    await expect(page).toHaveURL('/\/login\?next=\/bookings\/1$/');
    });


    test('after logout, going back does not show bookings', async ({ page }) => {
        const loginPage = new LoginPage(page);
        await loginPage.goto();
        await loginPage.login('acme', 'Acme@123');
        await expect(page).toHaveURL(/\/bookings$/);

        await page.getByTestId('logout').click();
        await expect(page).toHaveURL(/\/login$/);

        await page.goBack();

        await expect(page, 'must be sent back to login').toHaveURL(/\/login/);
        await expect(page.getByTestId('booking-row'), 'no booking data after logout').toHaveCount(0);
        });    
})