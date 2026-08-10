const title_field = document.getElementById('input');

async function getMovieTitle(query) {
    try {
        const response = await fetch(`/search-movie?q=${encodeURIComponent(query)}`);
        const data = await response.json();
        renderDropdown(data);
    } catch (err) {
        console.error("Error fetching movies:", err);
    }
}

function renderDropdown(movies) {
    const container = document.getElementById('search-results');
    container.innerHTML = '';

    if (!Array.isArray(movies) || movies.length === 0) {
        container.style.display = 'none';
        return;
    }

    movies.forEach(movie => {
        const title = movie.title || movie.Title;
        const releaseYear = (movie.release_date ? movie.release_date.split('-')[0] : '') || movie.Year || '';

        const item = document.createElement('button');
        item.type = 'button';
        item.className = 'dropdown-item d-flex justify-content-between align-items-center p-2';

        item.innerHTML = `
            <span class="fw-bold text-truncate">${title}</span>
            ${releaseYear ? `<small class="text-body-secondary ms-2">${releaseYear}</small>` : ''}
        `;

        item.addEventListener('click', () => {
            title_field.value = title;
            document.getElementById('poster_path').value = movie.poster_path || '';
            document.getElementById('tmdb_id').value = movie.id || '';
            container.innerHTML = '';
            container.style.display = 'none';
        });

        container.appendChild(item);
    });

    container.style.display = 'block';
}

title_field.addEventListener("input", () => {
    const title_value = title_field.value.trim();

    // Any manual typing invalidates a previous selection
    document.getElementById('poster_path').value = '';
    document.getElementById('tmdb_id').value = '';

    if (title_value.length >= 2) {
        getMovieTitle(title_value);
    } else {
        const container = document.getElementById('search-results');
        container.innerHTML = '';
        container.style.display = 'none';
    }
});

// Close dropdown when clicking outside
document.addEventListener('click', (event) => {
    const container = document.getElementById('search-results');
    if (container && !title_field.contains(event.target) && !container.contains(event.target)) {
        container.style.display = 'none';
    }
});