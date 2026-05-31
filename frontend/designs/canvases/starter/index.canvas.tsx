import type { TempoPage, TempoRouteStoryboard, TempoStoryboard } from "tempo-sdk";
import { Card } from "../../../components/Card";
import { Button } from "../../../components/Button";

const page: TempoPage = {
  name: "Starter",
};

export default page;

export const Home: TempoRouteStoryboard = {
  route: "/",
  name: "Home",
  layout: { x: 0, y: 0, width: 960, height: 720 },
};

export const DesignCard: TempoStoryboard = {
  render: () => (
    <Card label="Design" title="Visual-first editing">
      Select any element on the canvas and tweak styles, layout, and content
      without touching code.
    </Card>
  ),
  name: "Card (Design)",
  layout: { x: -20, y: 800, width: 310, height: 180 },
};

export const CodeCard: TempoStoryboard = {
  render: () => (
    <Card label="Code" title="Real code, always">
      Every change you make writes clean React code. No lock-in, no generated
      spaghetti.
    </Card>
  ),
  name: "Card (Code)",
  layout: { x: 325, y: 800, width: 310, height: 180 },
};

export const ShipCard: TempoStoryboard = {
  render: () => (
    <Card label="Ship" title="From idea to production">
      Preview, iterate, and push\u2014all from the same workspace. No
      context-switching.
    </Card>
  ),
  name: "Card (Ship)",
  layout: { x: 670, y: 800, width: 310, height: 180 },
};

export const PrimaryButton: TempoStoryboard = {
  render: () => <Button>Get started</Button>,
  name: "Button (Primary)",
  layout: { x: 280, y: 1060, width: 160, height: 60 },
};

export const OutlineButton: TempoStoryboard = {
  render: () => <Button variant="outline">Learn more</Button>,
  name: "Button (Outline)",
  layout: { x: 520, y: 1060, width: 180, height: 60 },
};
