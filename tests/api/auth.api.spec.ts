import { test, expect, PASSWORDS } from '../fixtures/api';

test.describe('Authentication', () => {
  test('valid login returns a working token and the correct role', async ({ request }) => {
    const res = await request.post('/api/auth/login', {
      data: { username: 'acme', password: PASSWORDS.acme },
    });

    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.access_token).toBeTruthy();
    expect(body.token_type).toBe('bearer');
    expect(body.role).toBe('customer');

    const me = await request.get('/api/me', {
      headers: { Authorization: `Bearer ${body.access_token}` },
    });
    expect(me.status(), 'token from login should work on /api/me').toBe(200);
    expect((await me.json()).username).toBe('acme');
  });


  test('reject wrong password and error 401', async ({ request }) => {
    const res = await request.post('/api/auth/login', {
      data: { username: 'acme', password: PASSWORDS.admin },
    });

    expect(res.status()).toBe(401);
    const body = await res.json();
    expect(body.detail).toBe("Invalid username or password");
  })

  test('reject unknown user with error 401 and message as Invalid username or password', async ({ request }) => {
    const res = await request.post('/api/auth/login', {
      data: { username: 'abcd', password: PASSWORDS.admin },
    });

    expect(res.status()).toBe(401);
    const body = await res.json();
    expect(body.detail).toBe("Invalid username or password");
  })


  test('No token in me api', async ({ request }) => {
    const res = await request.get('/api/me');

    expect(res.status()).toBe(401);
    const body = await res.json();
    expect(body.detail).toBe("Not authenticated");
  })


  test('Garbage token in me api', async ({ request }) => {
    const res = await request.get('/api/me', {
      headers: { Authorization: 'Bearer S4wtpZgZW5lmAnMW5YSr' },
    });

    expect(res.status()).toBe(401);
    const body = await res.json();
    expect(body.detail).toBe("Not authenticated");
  })
});