import { defineView, numericText } from "@wes/view-sdk";
import { definition } from "./contract";
import "./view.css";

const statusRole = {
  ok: "status-ok",
  degraded: "status-warn",
  down: "status-bad",
} as const;

export default defineView(definition, {
  Component: ({ input }) => {
    const names = input.services.map((service) => service.name);
    const duplicateNames = new Set(names).size !== names.length;

    return (
      <section className="service-board" aria-label={input.title}>
        <h2 className="screen-title">{input.title}</h2>
        {duplicateNames ? (
          <p className="status-bad" role="alert">
            Service names must be unique. Fix the input snapshot.
          </p>
        ) : input.services.length === 0 ? (
          <p className="screen-label" role="status">
            No services in this snapshot.
          </p>
        ) : (
          <div className="service-board-scroll">
            <table>
              <caption className="screen-label">
                Service health snapshot
              </caption>
              <thead>
                <tr>
                  <th className="screen-label" scope="col">Service</th>
                  <th className="screen-label" scope="col">Status</th>
                  <th className="screen-label" scope="col">Requests / s</th>
                  <th className="screen-label" scope="col">p95 / ms</th>
                </tr>
              </thead>
              <tbody>
                {input.services.map((service) => (
                  <tr key={service.name}>
                    <th className="table-key" scope="row">{service.name}</th>
                    <td>
                      <span
                        className={
                          `service-status ${statusRole[service.status]}`
                        }
                      >
                        {service.status}
                      </span>
                    </td>
                    <td className="table-value">{numericText(service.rps)}</td>
                    <td className="table-value">
                      {numericText(service.p95Ms)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    );
  },
});
