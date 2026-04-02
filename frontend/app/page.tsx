import Link from "next/link";

const benefits = [
  {
    title: "Búsqueda semántica",
    description:
      "Encontrá información sin recordar palabras exactas. El sistema entiende el significado de la pregunta, no solo las palabras clave.",
  },
  {
    title: "Respuestas con evidencia",
    description:
      "Cada respuesta incluye los fragmentos exactos del documento que la respaldan. Sin inventar datos, sin suposiciones.",
  },
  {
    title: "Aislamiento por organización",
    description:
      "Cada empresa opera sobre su propio espacio de conocimiento. Los datos nunca se mezclan entre organizaciones.",
  },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-white text-gray-900 font-sans">
      {/* Nav */}
      <nav className="border-b border-gray-100">
        <div className="max-w-6xl mx-auto px-8 py-4 flex items-center justify-between">
          <span className="text-lg font-semibold tracking-tight">Company Brain</span>
          <Link
            href="/app"
            className="text-sm font-medium text-gray-600 hover:text-gray-900 transition-colors"
          >
            Acceder →
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="max-w-6xl mx-auto px-8 py-28 text-center">
        <p className="text-xs font-semibold uppercase tracking-widest text-gray-400 mb-6">
          Plataforma de conocimiento empresarial
        </p>
        <h1 className="text-5xl font-bold leading-tight text-gray-900 mb-6">
          El conocimiento de tu empresa,
          <br />
          siempre disponible.
        </h1>
        <p className="text-lg text-gray-500 max-w-xl mx-auto mb-10 leading-relaxed">
          Company Brain centraliza la documentación interna y permite consultarla
          en lenguaje natural, con respuestas respaldadas por evidencia real.
        </p>
        <Link
          href="/app"
          className="inline-flex items-center px-7 py-3.5 bg-gray-900 text-white text-sm font-medium rounded-xl hover:bg-gray-700 transition-colors"
        >
          Ver demo
        </Link>
      </section>

      {/* Benefits */}
      <section className="bg-gray-50 border-t border-b border-gray-100">
        <div className="max-w-6xl mx-auto px-8 py-20">
          <h2 className="text-xl font-semibold text-gray-900 text-center mb-12">
            Para equipos que necesitan respuestas confiables
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {benefits.map((b) => (
              <div
                key={b.title}
                className="bg-white rounded-xl border border-gray-200 p-6"
              >
                <h3 className="text-sm font-semibold text-gray-900 mb-2">{b.title}</h3>
                <p className="text-sm text-gray-500 leading-relaxed">{b.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="max-w-6xl mx-auto px-8 py-24 text-center">
        <h2 className="text-2xl font-semibold text-gray-900 mb-3">Probalo ahora</h2>
        <p className="text-gray-500 mb-8 text-sm">
          Subí un documento y hacé tu primera consulta en segundos.
        </p>
        <Link
          href="/app"
          className="inline-flex items-center px-7 py-3.5 bg-gray-900 text-white text-sm font-medium rounded-xl hover:bg-gray-700 transition-colors"
        >
          Abrir la aplicación
        </Link>
      </section>

      {/* Footer */}
      <footer className="border-t border-gray-100">
        <div className="max-w-6xl mx-auto px-8 py-5 flex items-center justify-between">
          <span className="text-sm text-gray-400 font-medium">Company Brain</span>
          <span className="text-sm text-gray-300">© 2025</span>
        </div>
      </footer>
    </div>
  );
}
