import {test, expect} from '../fixtures/api';
import { futureDate, validBooking } from '../data/bookings';

test.describe('Create booking', () => {
    test('valid booking returns 201 with correct fields', async ({acmeApi}) => {
        const payload = validBooking();

        const res = await acmeApi.post('/api/bookings', {data: payload});

        expect(res.status()).toBe(201);
        const body = await res.json();
        expect(body.awb_number).toMatch(/^607-\d{8}$/);
        expect(body.status).toBe('BKD');
        expect(body.origin).toBe(payload.origin);
        expect(body.destination).toBe(payload.destination);
        expect(body.pieces).toBe(payload.pieces);
        expect(body.volumetric_kg).toBe(80);     
        expect(body.chargeable_kg).toBe(120.5);
    })

    const invalidCases = [
        { name: 'negative weight', change: { weight_kg: -100 }, error: 'weight_kg'},
        { name: 'weight 0', change: { weight_kg: 0 }, error: 'weight_kg' },
        { name: 'more then allowed weight', change: { weight_kg: 10000.1 }, error: 'weight_kg'},
        { name: 'same origin and destination', change: { destination: 'AUH' }, error: 'destination' },
        { name: 'unknown Airport code', change: { destination: 'XXX' }, error: 'destination' },
        { name: 'less then allowed pieces', change: { pieces: 0 }, error: 'pieces'},
        { name: 'more then allowed pieces', change: { pieces: 1000 }, error: 'pieces'},
        { name: 'past flight date', change: { flight_date: futureDate(-1) }, error: 'flight_date'},
        { name: 'blank commodity', change: { commodity: '   ' }, error: 'commodity'},
        { name: 'unknown special handling', change: { special_handling: 'ABC' }, error: 'special_handling'},
        { name: 'length_cm 0', change: { length_cm: 0 }, error: 'length_cm' },
        { name: 'more then allowed length_cm', change: { length_cm: 301 }, error: 'length_cm' },
        { name: 'width_cm 0', change: { width_cm: 0 }, error: 'width_cm' },
        { name: 'more then allowed width_cm', change: { width_cm: 301 }, error: 'width_cm' },
        { name: 'height_cm 0', change: { height_cm: 0 }, error: 'height_cm' },
        { name: 'more then allowed height_cm', change: { height_cm: 301 }, error: 'height_cm' },
    ];


    for (const c of invalidCases) {
        test(`rejects ${c.name} with 400`, async ({ acmeApi }) => {
        const res = await acmeApi.post('/api/bookings', { data: validBooking(c.change) });
        expect(res.status()).toBe(400);
        const body = await res.json();
        expect(body.errors.join(' ')).toContain(c.error);
        });
    }

    const boundaryValues = [
        { field: 'weight_kg', value: 10000 },
        { field: 'pieces', value: 1 },
        { field: 'pieces', value: 999 },
        { field: 'length_cm', value: 1 },
        { field: 'length_cm', value: 300 },
        { field: 'width_cm', value: 1 },
        { field: 'width_cm', value: 300 },
        { field: 'height_cm', value: 1 },
        { field: 'height_cm', value: 300 },
    ];

    for (const c of boundaryValues) {
        test(`accepts ${c.field} = ${c.value} with 201`, async ({ acmeApi }) => {
            const res = await acmeApi.post('/api/bookings', {
                data: validBooking({ [c.field]: c.value }),
            });

            expect(res.status(), `${c.field}=${c.value} should be accepted`).toBe(201);
            const body = await res.json();
            expect(body[c.field]).toBe(c.value);
        });
    }

    const requiredFields = ['origin', 'destination', 'pieces', 'weight_kg', 'length_cm', 'width_cm', 'height_cm', 'commodity', 'flight_date'];

    for (const field of requiredFields) {
        test(`rejects missing ${field} with 422`, async ({ acmeApi }) => {
            const payload: Record<string, unknown> = validBooking();
            delete payload[field];

            const res = await acmeApi.post('/api/bookings', { data: payload });
            expect(res.status()).toBe(422);
            const body = await res.json();
            expect(JSON.stringify(body.detail)).toContain(field);
        });
    }

    test('missing special_handling defaults to GEN', async ({ acmeApi }) => {
        const payload: Record<string, unknown> = validBooking();
        delete payload.special_handling;

        const res = await acmeApi.post('/api/bookings', { data: payload });
        expect(res.status()).toBe(201);
        expect((await res.json()).special_handling).toBe('GEN');
    });


    test('admin not allowed to make a booking and gets 403', async ({adminApi}) => {    
        const payload = validBooking();
        const res = await adminApi.post('/api/bookings', {data: payload});
        expect(res.status()).toBe(403);
    })


    test('globex cannot read an acme booking', async ({ acmeApi, globexApi }) => {        
        const res = await acmeApi.post('/api/bookings', { data: validBooking() });
        expect(res.status(), 'setup: booking should be created').toBe(201);
        const created = await res.json();

        const glob_res = await globexApi.get(`/api/bookings/${created.id}`);
        expect(glob_res.status(), 'globex must not see acme booking').toBe(404);
    });


    test('cancel a fresh booking, then cancelling again returns 409', async ({ acmeApi }) => {
        const res = await acmeApi.post('/api/bookings', { data: validBooking() });
        expect(res.status(), 'setup: booking should be created').toBe(201);
        const created = await res.json();

        const cancelRes = await acmeApi.post(`/api/bookings/${created.id}/cancel`);
        expect(cancelRes.status()).toBe(200);
        expect((await cancelRes.json()).status).toBe('CAN');

        const againRes = await acmeApi.post(`/api/bookings/${created.id}/cancel`);
        expect(againRes.status()).toBe(409);
    }); 


    const chargeableWeight = [
        { field: 'weight_kg', value: 100 },        
        { field: 'length_cm', value: 100 },
        { field: 'width_cm', value: 100 },
        { field: 'height_cm', value: 100 },
    ];


    test('chargeable weight uses volumetric weight, rounded up to 0.5 kg', async ({ acmeApi }) => {
        const res = await acmeApi.post('/api/bookings', {
            data: validBooking({ weight_kg: 100, length_cm: 100, width_cm: 100, height_cm: 100 }),
        });
        expect(res.status()).toBe(201);
        const body = await res.json();
        expect(body.volumetric_kg).toBeCloseTo(166.67, 2);
        expect(body.chargeable_kg).toBe(167.0);
    })
})