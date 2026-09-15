import { designs } from "../designs";

export function DesignGallery() {
  return (
    <main className="gallery-page">
      <header className="gallery-header">
        <div>
          <p className="eyebrow">Safe schema-aware analytics</p>
          <h1>Choose a working atmosphere.</h1>
          <p>
            Ten visual systems. One transparent query workflow. Open any route to test the complete
            interface.
          </p>
        </div>
        <span className="gallery-count">
          10
          <br />
          <small>design studies</small>
        </span>
      </header>
      <section className="design-grid">
        {designs.map((design) => (
          <a className={`design-card ${design.className}`} href={`/${design.id}`} key={design.id}>
            <div className="card-swatch" aria-hidden="true">
              <span>{design.id.padStart(2, "0")}</span>
              <i />
            </div>
            <div className="card-content">
              <span className="card-category">{design.category}</span>
              <h2>{design.name}</h2>
              <p>{design.description}</p>
              <span className="card-link">Open design /{design.id} →</span>
            </div>
          </a>
        ))}
      </section>
    </main>
  );
}
