// Open and close the menu on small screens

const toggleButton = document.getElementById("nav-toggle");
const navLinks = document.getElementById("nav-links");

toggleButton.addEventListener("click", function () {
    // toggle() adds the class "open" if it is missing, and removes it if it is there
    const isOpen = navLinks.classList.toggle("open");
    toggleButton.setAttribute("aria-expanded", isOpen);
});