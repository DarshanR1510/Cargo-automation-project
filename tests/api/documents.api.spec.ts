import { test, expect } from '../fixtures/api';
import { validBooking } from '../data/bookings';

test.describe('Documents', () => {

    const acceptedFiles = [
        { name: 'awb.pdf',    mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4 test content') },
        { name: 'max.pdf',    mimeType: 'application/pdf', buffer: Buffer.alloc(5 * 1024 * 1024) },
        { name: 'label.png',  mimeType: 'image/png',  buffer: Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]) },
        { name: 'photo.jpg',  mimeType: 'image/jpeg', buffer: Buffer.from([0xff, 0xd8, 0xff, 0xe0]) },
        { name: 'photo.jpeg', mimeType: 'image/jpeg', buffer: Buffer.from([0xff, 0xd8, 0xff, 0xe0]) },
        { name: 'INVOICE.PDF', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4 test content') },
    ];

    
  
    for (const c of acceptedFiles) {
        test(`uploads a ${c.name} and it can be downloaded unchanged`, async ({ acmeApi }) => {

            const bookingRes = await acmeApi.post('/api/bookings', { data: validBooking() });
            expect(bookingRes.status(), 'setup: booking should be created').toBe(201);
            const booking = await bookingRes.json();

            const content = c.buffer;
            
            const uploadRes = await acmeApi.post(`/api/bookings/${booking.id}/documents`, {
                multipart: { 
                    file: { 
                        name: c.name, 
                        mimeType: c.mimeType, 
                        buffer: content 
                    } 
                },
            });

            expect.soft(uploadRes.status()).toBe(201);
            const doc = await uploadRes.json();
            expect.soft(doc.filename).toBe(c.name);
            expect.soft(doc.size_bytes).toBe(content.length);

            const downloadRes = await acmeApi.get(`/api/documents/${doc.id}`);
            expect.soft(downloadRes.status()).toBe(200);
            expect.soft(await downloadRes.body()).toEqual(content);
        });
    }

    const rejectedFiles = [
        { name: 'malware.exe', mimeType: 'application/octet-stream', buffer: Buffer.from('MZ fake exe content'), status: 400, error: "Only PDF, PNG and JPG files are allowed" },
        { name: 'empty.pdf',   mimeType: 'application/pdf', buffer: Buffer.alloc(0), status: 400, error: "File is empty" },
        { name: 'large.pdf',   mimeType: 'application/pdf', buffer: Buffer.alloc(6 * 1024 * 1024), status: 413, error: "File is larger than 5 MB" },
    ];

    for (const c of rejectedFiles) {
        test(`uploads a ${c.name} and it should be rejected`, async ({ acmeApi }) => {

            const bookingRes = await acmeApi.post('/api/bookings', { data: validBooking() });
            expect(bookingRes.status(), 'setup: booking should be created').toBe(201);
            const booking = await bookingRes.json();

            const content = c.buffer;
            
            const uploadRes = await acmeApi.post(`/api/bookings/${booking.id}/documents`, {
                multipart: { 
                    file: { 
                        name: c.name, 
                        mimeType: c.mimeType, 
                        buffer: content 
                    } 
                },
            });

            expect.soft(uploadRes.status()).toBe(c.status);
            const body = await uploadRes.json();            
            expect(body.detail).toBe(c.error);
        });
    }


    test("reject rename file, should throw error", async ( {acmeApi}) => {
        const bookingRes = await acmeApi.post('/api/bookings', { data: validBooking() });
            expect(bookingRes.status(), 'setup: booking should be created').toBe(201);
            const booking = await bookingRes.json();

            const content = Buffer.from('MZ fake exe content');
            
            const uploadRes = await acmeApi.post(`/api/bookings/${booking.id}/documents`, {
                multipart: { 
                    file: { 
                        name: 'invoice.pdf', 
                        mimeType: 'application/pdf', 
                        buffer: content 
                    } 
                },
            });

            expect.soft(uploadRes.status()).toBe(201);            
    });


    test("reject someone else's booking", async ( {acmeApi, globexApi} ) => {
        const bookingRes = await acmeApi.post('/api/bookings', { data: validBooking() });
            expect(bookingRes.status(), 'setup: booking should be created').toBe(201);
            const booking = await bookingRes.json();

            const content = Buffer.from('%PDF-1.4 test content');
            
            const uploadRes = await globexApi.post(`/api/bookings/${booking.id}/documents`, {
                multipart: { 
                    file: { 
                        name: 'invoice.pdf', 
                        mimeType: 'application/pdf', 
                        buffer: content 
                    } 
                },
            });

            expect.soft(uploadRes.status()).toBe(404);            
    });


    test("accept uppercase extension", async ( {acmeApi} ) => {
        const bookingRes = await acmeApi.post('/api/bookings', { data: validBooking() });
            expect(bookingRes.status(), 'setup: booking should be created').toBe(201);
            const booking = await bookingRes.json();

            const content = Buffer.from('%PDF-1.4 test content');
            
            const uploadRes = await acmeApi.post(`/api/bookings/${booking.id}/documents`, {
                multipart: { 
                    file: { 
                        name: 'INVOICE.PDF', 
                        mimeType: 'application/pdf', 
                        buffer: content 
                    } 
                },
            });

            expect.soft(uploadRes.status()).toBe(201);  
            const doc = await uploadRes.json();
            expect.soft(doc.filename).toBe('INVOICE.PDF');
            expect.soft(doc.size_bytes).toBe(content.length);          
    });

});