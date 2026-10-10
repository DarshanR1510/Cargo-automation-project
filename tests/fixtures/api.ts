import { test as base, expect, APIRequestContext, PlaywrightWorkerArgs } from '@playwright/test';

export type User = 'acme' | 'globex' | 'admin';

export const PASSWORDS: Record<User, string> = {
  acme: 'Acme@123',
  globex: 'Globex@123',
  admin: 'Admin@123',
};

export async function loginToken(
  playwright: PlaywrightWorkerArgs['playwright'],
  baseURL: string,
  user: User,
    ): Promise<string> {
    const anon = await playwright.request.newContext({ baseURL });
    const res = await anon.post('/api/auth/login', {
        data: { username: user, password: PASSWORDS[user] },
    });
    expect(res.status(), `login as ${user}`).toBe(200);
    const body = await res.json();
    await anon.dispose();
    return body.access_token;
}

async function apiAs(playwright: PlaywrightWorkerArgs['playwright'], baseURL: string, user: User) {
  const token = await loginToken(playwright, baseURL, user);
  return playwright.request.newContext({
    baseURL,
    extraHTTPHeaders: { Authorization: `Bearer ${token}` },
  });
}

type ApiFixtures = {
  acmeApi: APIRequestContext;
  globexApi: APIRequestContext;
  adminApi: APIRequestContext;
};

export const test = base.extend<ApiFixtures>({
  acmeApi: async ({ playwright, baseURL }, use) => {
    const ctx = await apiAs(playwright, baseURL!, 'acme');
    await use(ctx);
    await ctx.dispose();
  },
  globexApi: async ({ playwright, baseURL }, use) => {
    const ctx = await apiAs(playwright, baseURL!, 'globex');
    await use(ctx);
    await ctx.dispose();
  },
  adminApi: async ({ playwright, baseURL }, use) => {
    const ctx = await apiAs(playwright, baseURL!, 'admin');
    await use(ctx);
    await ctx.dispose();
  },
});

export { expect };