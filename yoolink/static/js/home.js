var currentDesktopSlideId = 1;
var currentHandySlideId = 1;
// Slider
var desktopSliderElement = document.getElementById("desktopSlider");
var totalDesktopSlides = desktopSliderElement.childElementCount;
var handySliderElement = document.getElementById("handySlider");
var totalHandySlides = handySliderElement.childElementCount;
let myInterval = setInterval(next, 7000);

const browser = document.querySelector("#browser");
const phone = document.querySelector("#phone");

const content1 = document.querySelector("#content1");
const arrow1 = document.querySelector("#arrow1");
const content2 = document.querySelector("#content2");
const arrow2 = document.querySelector("#arrow2");
const content3 = document.querySelector("#content3");
const arrow3 = document.querySelector("#arrow3");
const content4 = document.querySelector("#content4");
const arrow4 = document.querySelector("#arrow4");

const responsive = document.querySelector("#Responsive");

//Responsive Design


//hier noch magin ändern 
function toggleResponsive() {
  if (phone.classList.contains("hidden")) {
    responsive.classList.remove("xs:-mb-48");
    browser.classList.add("hidden");
    phone.classList.remove("hidden");
  } else {
    responsive.classList.add("xs:-mb-48");
    browser.classList.remove("hidden");
    phone.classList.add("hidden");
  }
}

// Image slider
function next() {
  if (phone.classList.contains("hidden")) {
    // Desktop is shown
    if (currentDesktopSlideId < totalDesktopSlides) {
      currentDesktopSlideId++;
      showSlide("desktopSlider");
    } else {
      currentDesktopSlideId = 1;
      showSlide("desktopSlider");
    }
  } else {
    if (currentHandySlideId < totalHandySlides) {
      currentHandySlideId++;
      showSlide("handySlider");
    } else {
      currentHandySlideId = 1;
      showSlide("handySlider");
    }
  }
  
  clearInterval(myInterval);
  myInterval = setInterval(next, 7000);
}

/*function prev() {
  if (currentSlideId > 1) {
    currentSlideId--;
    showSlide();
  } else {
    currentSlideId = totalSlides;
    showSlide();
  }
  clearInterval(myInterval);
  myInterval = setInterval(next, 7000);
}*/

function showSlide(id) {

  if(id === 'desktopSlider') {
    slides = document.getElementById(id).getElementsByTagName("img");
    for (let index = 0; index < totalDesktopSlides; index++) {
      const element = slides[index];
      if (currentDesktopSlideId == index + 1) {
        element.classList.add("animate-fade-in-down");
        element.classList.remove("hidden");
      } else {
        element.classList.add("hidden");
        element.classList.remove("animate-fade-in-down");
      }
    }
  } else {
    slides = document.getElementById(id).getElementsByTagName("img");
    for (let index = 0; index < totalHandySlides; index++) {
      const element = slides[index];
      if (currentHandySlideId == index + 1) {
        element.classList.add("animate-fade-in-down");
        element.classList.remove("hidden");
      } else {
        element.classList.add("hidden");
        element.classList.remove("animate-fade-in-down");
      }
    }
  }

  
}


var csrfTokenInput = document.querySelector('input[name="csrfmiddlewaretoken"]');
var csrfToken = csrfTokenInput ? csrfTokenInput.value : undefined;

// JQuery functions
$(document).ready(function() {
  // FAQ Toggle
  $(".faq-toggle").click(function() {
    var content = $(this).siblings(".faq-content");
    var arrow = $(this).find(".faq-arrow");
    
    if (content.hasClass("hidden")) {
      content.removeClass("hidden");
      arrow.addClass("rotate-180");
    } else {
      content.addClass("hidden");
      arrow.removeClass("rotate-180");
    }
  });
  /**
   * Email Form submit Function (index page)
   * How to use: Compare wukschweiss project
   */
  $('#emailForm').submit(function(event) {
    event.preventDefault(); // Prevent the default form submission
    var formData = {
        name: $('#name').val(),
        email: $('#email').val(),
        title: $('#subject').val(),
        message: $('#message').val(),
        csrfmiddlewaretoken: csrftoken,
    };
    // Send form data to the server using AJAX
    $.ajax({
        type: 'POST',
        url: '/cms/email/request/',
        data: formData,
        success: function(response) {
            // Handle successful response here
            if(response.success) {
              sendNotif("Ihre Nachricht wurde erfolgreich gesendet", "success")
            }
            $('#emailForm')[0].reset();
        },
        error: function(xhr, status, error) {
            // Handle error response here
            sendNotif("Etwas ist schief gelaufen. Versuchen Sie es bitte später nochmal.", "error")
        }
    });
});
});

