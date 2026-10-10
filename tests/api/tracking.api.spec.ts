import { test, expect } from '../fixtures/api';
import { validBooking } from '../data/bookings';


test.describe("Tracking", () => {

    const diffSpecialHandling = [
        'GEN', 'DGR', 'PER', 'PIL', 'AVI'
    ];

    for (const c of diffSpecialHandling) {
        test(`Track a new ${c} booking by AWB`, async ({ acmeApi, request }) => {              
            const res = await acmeApi.post('/api/bookings', { data: validBooking({ special_handling: c }) });
            expect(res.status(), 'setup: booking should be created').toBe(201);

            const created = await res.json();
            const awb_num = created.awb_number
            expect(awb_num).toMatch(/^607-\d{8}$/);

            const tracking_res = await request.get(`/api/tracking/${awb_num}`);
            expect(tracking_res.status(), 'tracking status code').toBe(200);

            const track_received = await tracking_res.json();
            expect(track_received.awb_number).toBe(awb_num);
            expect(track_received.status).toBe('BKD');
            expect(track_received.events).toHaveLength(1);
            expect(track_received.events[0].milestone).toBe('BKD');
        })
    }

    const awbNumbers = [
        '607-12345670',     // wrong check-in digit         400
        'AWB-4747474A',     // Alphabets in AWB number      400
        '60799999993'       // no - in AWB number           400
    ];

    for (const awb of awbNumbers) {
        test(`Reject wrong formatted AWB ${awb}`, async ({ request }) => {
            const res = await request.get(`/api/tracking/${awb}`);
            expect(res.status()).toBe(400);
        })
    }


    const unknownAWBNumber = [
        '607-99999992',     // unknown AWB number           404        
        '999-12345675',     // incorrect airline prefix     404
    ];
    for (const awb of unknownAWBNumber) {
        test(`Reject unknown AWB ${awb}`, async ({ request }) => {
            const res = await request.get(`/api/tracking/${awb}`);
            expect(res.status()).toBe(404);
        })
    }


    test("Accept Admin records RCS on a fresh booking", async ({ acmeApi, adminApi, request }) => {              
        const res = await acmeApi.post('/api/bookings', { data: validBooking() });
        expect(res.status(), 'setup: booking should be created').toBe(201);

        const created = await res.json();
        const awb_num = created.awb_number
        const booking_id = created.id        
        expect(created.status).toBe('BKD');

        const admin_res = await adminApi.post(`/api/bookings/${booking_id}/events`, 
            {data: { "milestone": "RCS", "location": "AUH" }} );

        expect(admin_res.status()).toBe(201);

        const tracking_res = await request.get(`/api/tracking/${awb_num}`);
        expect(tracking_res.status(), 'tracking status code').toBe(200);

        const track_received = await tracking_res.json();
        expect(track_received.awb_number).toBe(awb_num);
        expect(track_received.status).toBe('RCS');
        expect(track_received.events).toHaveLength(2);
        expect(track_received.events[0].milestone).toBe('BKD');
        expect(track_received.events[1].milestone).toBe('RCS');
    });


    test("reject Admin records DLV straight after BKD", async ({ acmeApi, adminApi, request }) => {              
        const res = await acmeApi.post('/api/bookings', { data: validBooking() });
        expect(res.status(), 'setup: booking should be created').toBe(201);

        const created = await res.json();
        const awb_num = created.awb_number
        const booking_id = created.id        

        const admin_res = await adminApi.post(`/api/bookings/${booking_id}/events`, 
            {data: { "milestone": "DLV", "location": "AUH" }} );

        expect.soft(admin_res.status(), 'skipping milestone must be rejected').toBe(409);

        const tracking_res = await request.get(`/api/tracking/${awb_num}`);
        expect(tracking_res.status(), 'tracking status code').toBe(200);

        const track_received = await tracking_res.json();
        expect.soft(track_received.status, 'status must stay BKD after a rejected event').toBe('BKD');
        expect.soft(track_received.events, 'no new event should be added').toHaveLength(1);
    });


    test("reject Customer tries to record a milestone", async ({ acmeApi, request }) => {              
        const res = await acmeApi.post('/api/bookings', { data: validBooking() });
        expect(res.status(), 'setup: booking should be created').toBe(201);

        const created = await res.json();
        const awb_num = created.awb_number
        const booking_id = created.id        

        const cust_res = await acmeApi.post(`/api/bookings/${booking_id}/events`, 
            {data: { "milestone": "RCS", "location": "AUH" }} );

        expect(cust_res.status()).toBe(403);

        const tracking_res = await request.get(`/api/tracking/${awb_num}`);
        expect(tracking_res.status(), 'tracking status code').toBe(200);

        const track_received = await tracking_res.json();
        expect(track_received.status).toBe('BKD');
        expect(track_received.events).toHaveLength(1);
    });
})
