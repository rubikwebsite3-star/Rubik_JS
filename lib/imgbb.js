const axios = require('axios');
const FormData = require('form-data');
require('dotenv').config();

const IMGBB_API_KEY = process.env.IMGBB_API_KEY || "f4d21e33dfe671434b7306e2a1abd8e5";

async function uploadToImgBB(fileBuffer, fileName) {
    try {
        const form = new FormData();
        form.append('key', IMGBB_API_KEY);
        form.append('image', fileBuffer, { filename: fileName });

        const response = await axios.post('https://api.imgbb.com/1/upload', form, {
            headers: {
                ...form.getHeaders()
            }
        });

        if (response.data && response.data.data) {
            return {
                url: response.data.data.url,
                delete_url: response.data.data.delete_url
            };
        }
    } catch (error) {
        console.error('ImgBB Upload Error:', error.response ? error.response.data : error.message);
    }
    return { url: null, delete_url: null };
}

async function deleteFromImgBB(deleteUrl) {
    if (!deleteUrl) return;
    try {
        // ImgBB doesn't have a direct API for deletion with the delete_url via a simple DELETE request usually.
        // The delete_url is often a web page with a confirmation button.
        // However, the original Django code tried to scrape the auth_token.
        // We'll implement a similar logic if possible, or just log it.
        
        const response = await axios.get(deleteUrl);
        const match = response.data.match(/name="auth_token"\s+value="([^"]+)"/);
        if (match) {
            const authToken = match[1];
            await axios.post(deleteUrl, `auth_token=${authToken}&action=delete`, {
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded'
                }
            });
        }
    } catch (error) {
        console.error('ImgBB Delete Error:', error.message);
    }
}

module.exports = { uploadToImgBB, deleteFromImgBB };
