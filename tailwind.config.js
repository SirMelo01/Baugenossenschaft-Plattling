/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./yoolink/templates/*.{html,js}",
            "./yoolink/templates/components/*.{html,js}",
            "./yoolink/templates/pages/*.{html,js}",
            "./yoolink/templates/pages/**/*.{html,js}",
            "./yoolink/templates/pages/cms/*.{html,js}",
            "./yoolink/templates/pages/cms/**/*.{html,js}",
            "./yoolink/templates/pages/cms/orders/**/*.{html,js}",
            "./yoolink/templates/pages/cms/galery/*.{html,js}",
            "./yoolink/templates/designs/*.{html,js}",
            "./yoolink/templates/blog/*.{html,js}",
            "./yoolink/templates/registration/*.{html,js}",
            "./yoolink/templates/pages/cms/content/*.{html,js}",
            "./yoolink/templates/pages/cms/content/sites/*.{html,js}",
            "./yoolink/templates/pages/cms/content/sites/**/*.{html,js}",
            "./yoolink/templates/pages/cms/blog/*.{html,js}",
            "./yoolink/static/js/**/*.js",
            "./yoolink/blog/**/*.py",
            "./yoolink/ycms/applications/blog/**/*.py"
            ],
  theme: {
    screens: {
      xs: "320px",
      sm: "480px",
      md: "768px",
      lg: "976px",
      xl: "1440px",
      xxl: "1600px",
    },
    extend: {
      variants: {
        scale: ["responsive", "hover", "focus", "group-hover"],
        textColor: ["responsive", "hover", "focus", "group-hover"],
        opacity: ["responsive", "hover", "focus", "group-hover"],
        backgroundColor: ["responsive", "hover", "focus", "group-hover"],
      },
      boxShadow: {
        outline: "0 0 0 3px rgba(101, 31, 255, 0.4)",
      },
      height: {
        129: "400px",
        130: "590px",
        131: "590px",
      },
      keyframes: {
        "fade-in-down": {
          "0%": {
            opacity: "0",
          },
          "100%": {
            opacity: "1",
          },
        }
      },
      animation: {
        "fade-in-down": "fade-in-down 1.2s ease-out",
      },
      keyframes: {
        fadeOut: {
          '0%': { opacity: '1' },
          '100%': { opacity: '0' },
        },
      },
      animation: {
        'fade-out':      'fadeOut 1s ease-out 1 forwards 1.2s',
      },
      fontFamily: {
        raleway: ['"Raleway"', 'sans-serif'],
        poppins: ['"Poppins"', 'poppins-light'],
        roboto: ['"Roboto"', 'ui-sans-serif', 'system-ui', '-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', '"Helvetica Neue"', 'Arial', '"Noto Sans"', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
