/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            fontFamily: {
                christmas: ['"Mountains of Christmas"', 'cursive'],
                inter: ['Inter', 'sans-serif'],
            },
            colors: {
                christmas: {
                    red: '#b21f1f',
                    gold: '#fdbb2d',
                    blue: '#1a2a6c',
                }
            }
        },
    },
    plugins: [],
}
